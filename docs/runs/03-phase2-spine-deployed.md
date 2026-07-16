# Phase 2 — infra spine deployed and proven with the model stubbed

Date: 2026-07-16

## Goal

Stand up the cloud spine (provider-agnostic, no model yet) and prove the whole
nightly path runs end to end in AWS: local rollup to ingest to DynamoDB, then the
reasoning agent reads it, judges avoidance deterministically, calls the stubbed
model, writes the brief, and hands it to the stubbed delivery.

## What was built and deployed (us-east-1)

- CDK, two stacks: `sc-dev-data` (one DynamoDB table, single-table design) and
  `sc-dev-api` (lambdas, API Gateway, EventBridge Scheduler).
- Ingest lambda behind `POST /ingest`, API key required (the endpoint is public and
  writes to a personal table, so an open write path would be wrong; the key is
  AWS-managed so nothing secret sits in the repo).
- Reasoning lambda, the nightly agent: reads the recent rollups and per-skill state,
  runs the deterministic avoidance analysis, calls the model seam, writes the brief
  and today's drill.
- `analysis.py`: the deterministic core. Exam blueprints (CKA/CKS/CKAD weights and
  deadlines), the topic-to-domain mapping per exam, and the gap and decay math.
- `model.py`: the model seam, STUBBED. Typed input and output, a loud TODO, output
  tagged `source="STUB"`. It does not call Gemini.
- `delivery.py`: brief formatting is real; Telegram and email sends are STUBBED and
  log exactly what they would send.
- EventBridge Scheduler at 03:00 Africa/Lagos (timezone-aware, no UTC/DST math).

## Proof (real, live)

- Local rollup POSTed today's real data to the live ingest: HTTP 200, 73 events
  stored, 8 skills stamped.
- Invoked the reasoning lambda: HTTP 200, wrote the brief to DynamoDB.
- The brief, read back from DynamoDB, has `focus_domain=troubleshooting` (the
  correctly-identified most-avoided CKA domain) and `model_source=STUB`.
- CloudWatch shows the stubbed delivery logging the full morning brief for both
  channels, every stub piece clearly labelled, real deterministic panels intact
  (days to exam, top avoided, decaying skills). Cold start 532ms, run 125ms.

## Two real bugs the live run caught (not caught locally)

- DynamoDB returns numbers as `decimal.Decimal`, so the weight math threw
  `float - Decimal`. Fixed by casting event counts to int as they enter the math.
- DynamoDB `put_item` refuses `float`. Fixed with a `to_dynamo` helper that
  round-trips through JSON to turn every float into a Decimal before writing.
- Also hit, and it was expected: API Gateway rejected the key for about a minute
  after deploy with 403 while the usage plan propagated, then accepted it.

## Boundary reached

The spine is live and the nightly path works with everything stubbed. The local
cron now points at the real ingest (rollup/.env, gitignored). Phase 3 swaps the
model stub for a real gemini-2.5-flash call, wires real Telegram and email, and
builds the dashboard, once the credentials are handed over.
