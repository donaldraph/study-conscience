import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';

interface DataStackProps extends cdk.StackProps {
  stage: string;
}

/**
 * Storage layer — one DynamoDB table, single-table design keyed by a typed PK.
 *
 *   PK           SK             what it is
 *   ----------   ------------   ------------------------------------------------
 *   ROLLUP       <YYYY-MM-DD>   a day's activity rollup, as shipped by the local cron
 *   SKILL        <skill-name>   per-skill state: last practised, counts, decay
 *   DRILL        <YYYY-MM-DD>   the drill generated for a day, plus its later grade
 *   BRIEF        <YYYY-MM-DD>   the morning brief the reasoning lambda produced
 *
 * Reads the reasoning lambda needs:
 *   last N rollups -> Query(PK=ROLLUP) newest-first, Limit N
 *   all skill state -> Query(PK=SKILL)
 * A single partition per type is fine: this is a personal, once-a-day tool.
 */
export class DataStack extends cdk.Stack {
  public readonly table: dynamodb.Table;

  constructor(scope: Construct, id: string, props: DataStackProps) {
    super(scope, id, props);
    const isProd = props.stage === 'prod';

    this.table = new dynamodb.Table(this, 'Study', {
      tableName: `sc-study-${props.stage}`,
      partitionKey: { name: 'PK', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'SK', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      pointInTimeRecovery: isProd,
      removalPolicy: isProd ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
    });

    new cdk.CfnOutput(this, 'TableName', { value: this.table.tableName });
  }
}
