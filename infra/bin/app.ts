#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { DataStack } from '../lib/data-stack';

const app = new cdk.App();

// Stage drives naming and prod-vs-dev behaviour. Override: cdk deploy --all -c stage=prod
const stage = app.node.tryGetContext('stage') || 'dev';

const env: cdk.Environment = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
};

const prefix = `sc-${stage}`;

// Storage layer — the one table every other stack reads and writes.
new DataStack(app, `${prefix}-data`, { env, stage });

cdk.Tags.of(app).add('project', 'study-conscience');
cdk.Tags.of(app).add('stage', stage);
