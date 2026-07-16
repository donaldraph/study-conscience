# Study Conscience

A nightly, unattended AI agent that reads my real Kubernetes study activity and
tells me which CNCF exam domains I am *avoiding*, not just what I studied.

Every night it reads the API server audit log from my local kind cluster, maps
each command to a CKA / CKS / CKAD exam domain, weighs the activity against the
official domain weightings and days-to-deadline, and sends a morning brief with
one targeted drill for the domain I have been quietly skipping.

Built for the AWS Builder Center "Always-On Agent Weekend Challenge".

## Why avoidance, not coverage

Counting what I studied needs no AI and would be AI-washing. The load-bearing
judgment is deciding which domain is *avoided* versus genuinely mastered versus
simply not-yet-started, given the exam weights and how close each deadline is,
and then generating a drill that targets the gap. That judgment is the agent's
job. Roughly 70 percent of the command-to-domain mapping is deterministic rules;
the model earns its place on the ambiguous residue and the avoidance narrative.

## Exams tracked

| Exam | My deadline | Pass |
|------|-------------|------|
| CKA  | 2026-11-30  | 66%  |
| CKS  | 2027-02     | 67%  |
| CKAD | 2027-04     | 66%  |

All three run on Kubernetes v1.35. My kind cluster runs v1.35.1 to match.

## Stack

- **kind (v1.35.1)**: local study cluster with API server audit logging enabled
- **rollup script (Python)**: runs locally, parses the audit log, rolls it into a
  compact daily JSON, POSTs it to the ingest endpoint. Raw audit logs never leave
  the box.
- **EventBridge Scheduler**: nightly cron trigger (~03:00 WAT)
- **Lambda (Python 3.12)**: ingest handler + reasoning handler
- **DynamoDB**: daily activity rollups, per-skill state, drill history
- **API Gateway**: ingest endpoint (local cron POSTs here) + read endpoint
- **Secrets Manager**: Gemini API key, Telegram token, email creds
- **CDK (TypeScript)**: data / api / hosting stacks
- **Frontend (S3 + CloudFront)**: domain-coverage heatmap + avoidance trend

## Current status

Phases 1 and 2 done and deployed to AWS (us-east-1). The whole nightly path runs
end to end with the model stubbed: real audit data rolls up locally, POSTs to the
keyed ingest, lands in DynamoDB, the reasoning agent judges avoidance
deterministically and writes the morning brief, and the stubbed delivery logs
exactly what it would send. Phase 3 (real model, real delivery, dashboard) is next.
See BUILD_LOG.md for the running journal and docs/runs for the proofs.

The model layer (Google Gemini, gemini-2.5-flash) and both delivery channels
(Telegram, email) are **stubbed** for now: typed input and output, a clear TODO,
and hardcoded sample data that is obviously labelled as a stub. They get wired to
real credentials in Phase 3. Nothing in this repo presents stub output as real
model output.

## Build order

1. **Phase 1** (local data path, the real risk): audit logging on, local rollup
   script, cron, proven end-to-end with real cluster data.
2. **Phase 2** (infra spine, provider-agnostic): CDK stacks, ingest Lambda,
   reasoning Lambda with deterministic domain math and a stubbed model call,
   nightly trigger, stubbed delivery.
3. **Phase 3** (live): real Gemini call, real Telegram + email, dashboard.
