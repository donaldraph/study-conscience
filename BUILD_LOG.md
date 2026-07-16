# Build log

Running journal at RUN-MD standard: symptom / root cause / fix / reasoning, in
real time. Newest entries at the top of each phase.

## Phase 1 — local data path

### 2026-07-16 — repo scaffold

- Created the public repo and the skeleton (README, .gitignore, this log).
- Local git identity pinned to DonaldRaph on this shared machine before the first
  commit.
- Decisions locked with the operator: recreate the `study` kind cluster (nothing
  precious in it), Phase-1 boundary is real audit data to rollup to correct daily
  JSON to a POST verified against a local mock. Real ingest endpoint is Phase 2.

### Environment facts at start

- `study` kind cluster already runs `kindest/node:v1.35.1`, the exam version.
- Audit logging was NOT enabled: no audit flags in the live kube-apiserver static
  pod manifest. Confirmed before starting, so Step 1 is real work.
- `kubectl config get-contexts` was empty. Audit extraction uses `docker exec` so
  this does not block ingestion, but the cluster recreate re-exports the context.
- Toolchain present: kind v0.32.0, node v22, cdk 2.1131, python 3.12.3, aws-cli,
  gh authed as donaldraph with repo + delete_repo scopes.
