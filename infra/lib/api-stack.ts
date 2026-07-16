import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigw from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as scheduler from 'aws-cdk-lib/aws-scheduler';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as path from 'path';

const GEMINI_SECRET_NAME = 'study-conscience/gemini';

interface ApiStackProps extends cdk.StackProps {
  stage: string;
  table: dynamodb.Table;
}

/**
 * Compute + API. For now: the ingest lambda behind API Gateway, so the local
 * nightly cron can POST its rollup. The reasoning lambda, its schedule, and the
 * read routes for the dashboard land in later commits.
 *
 * POST /ingest requires an API key. The endpoint is public (the local box has no
 * fixed IP), and it writes to a personal table, so an unauthenticated write path
 * would be wrong. The key is AWS-managed, so nothing secret sits in this repo.
 */
export class ApiStack extends cdk.Stack {
  public readonly api: apigw.RestApi;

  constructor(scope: Construct, id: string, props: ApiStackProps) {
    super(scope, id, props);
    const { table } = props;

    const lambdasPath = path.join(__dirname, '..', 'lambdas');
    const commonEnv = {
      TABLE_NAME: table.tableName,
      APP_TZ: this.node.tryGetContext('appTz') || 'Africa/Lagos',
    };

    const makeFn = (
      name: string,
      handler: string,
      extraEnv: Record<string, string> = {},
      timeoutSeconds = 10,
      memoryMb = 256,
    ) =>
      new lambda.Function(this, name, {
        runtime: lambda.Runtime.PYTHON_3_12,
        code: lambda.Code.fromAsset(lambdasPath),
        handler,
        timeout: cdk.Duration.seconds(timeoutSeconds),
        memorySize: memoryMb,
        environment: { ...commonEnv, ...extraEnv },
        tracing: lambda.Tracing.ACTIVE,
      });

    const ingestFn = makeFn('IngestFn', 'ingest.handler');
    table.grantReadWriteData(ingestFn);

    // The nightly agent: reads rollups, judges avoidance, writes the brief + drill.
    // 60s timeout and 512MB give the Gemini generate-and-grade call room to breathe.
    const geminiSecret = secretsmanager.Secret.fromSecretNameV2(this, 'GeminiSecret', GEMINI_SECRET_NAME);
    const reasoningFn = makeFn(
      'ReasoningFn',
      'reasoning.handler',
      {
        GEMINI_SECRET_NAME,
        // gemini-flash-lite-latest: reliable + free-tier friendly. The pinned
        // gemini-2.5-flash models are gated for new accounts; the *-latest aliases
        // are not. Override with -c model=... at deploy.
        MODEL_ID: this.node.tryGetContext('model') || 'gemini-flash-lite-latest',
      },
      60,
      512,
    );
    table.grantReadWriteData(reasoningFn);
    geminiSecret.grantRead(reasoningFn);

    // EventBridge Scheduler at 03:00 Africa/Lagos. Scheduler (not a plain rule) so
    // the schedule is timezone-aware and never needs UTC/DST hand-math.
    const schedulerRole = new iam.Role(this, 'SchedulerRole', {
      assumedBy: new iam.ServicePrincipal('scheduler.amazonaws.com'),
    });
    reasoningFn.grantInvoke(schedulerRole);

    new scheduler.CfnSchedule(this, 'NightlyBrief', {
      name: `sc-${props.stage}-nightly-brief`,
      description: 'Runs the study-conscience agent every night at 03:00 Africa/Lagos.',
      flexibleTimeWindow: { mode: 'OFF' },
      scheduleExpression: 'cron(0 3 * * ? *)',
      scheduleExpressionTimezone: 'Africa/Lagos',
      target: {
        arn: reasoningFn.functionArn,
        roleArn: schedulerRole.roleArn,
        retryPolicy: { maximumRetryAttempts: 2 },
      },
    });

    this.api = new apigw.RestApi(this, 'Api', {
      restApiName: `sc-${props.stage}`,
      deployOptions: { stageName: props.stage, tracingEnabled: true },
      defaultCorsPreflightOptions: {
        allowOrigins: apigw.Cors.ALL_ORIGINS, // TODO: lock to the CloudFront origin
        allowMethods: apigw.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type', 'x-api-key'],
      },
    });

    // POST /ingest -> store a daily rollup. API key required.
    this.api.root
      .addResource('ingest')
      .addMethod('POST', new apigw.LambdaIntegration(ingestFn), { apiKeyRequired: true });

    const key = this.api.addApiKey('IngestKey', { apiKeyName: `sc-${props.stage}-ingest` });
    const plan = this.api.addUsagePlan('IngestPlan', {
      name: `sc-${props.stage}-ingest`,
      throttle: { rateLimit: 5, burstLimit: 10 },
      apiStages: [{ api: this.api, stage: this.api.deploymentStage }],
    });
    plan.addApiKey(key);

    new cdk.CfnOutput(this, 'ApiUrl', { value: this.api.url });
    new cdk.CfnOutput(this, 'IngestKeyId', { value: key.keyId });
  }
}
