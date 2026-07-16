# Build log

Running journal at RUN-MD standard: symptom / root cause / fix / reasoning, in
real time. Newest entries at the top of each phase.

## Phase 3 — live model and delivery

### 2026-07-16 — Gemini wired and proven live

- Replaced the model stub with a real Gemini call: structured JSON output against a
  response schema, key from Secrets Manager, three-try backoff on 429/503, and a
  clearly-labelled stub fallback so the nightly job never crashes when the model is
  down. Model id is configurable; default gemini-flash-lite-latest.
- Proven live: the reasoning lambda produced a real avoidance judgment that quotes
  the actual numbers (Troubleshooting 30% weight vs 1.4% activity, gap 0.286, 137
  days) and a valid multi-line drill manifest.

### 2026-07-16 — the model I was told to use is gated, and lite flattened YAML

- Symptom A: `gemini-2.5-flash` (and `-lite`) returned 404 "no longer available to
  new users" on generateContent, even though models.list showed them.
- Root cause: pinned 2.5 models are gated for new accounts. The `*-latest` aliases
  are not. `gemini-flash-latest` and `gemini-3.5-flash` were slow / 503 under load;
  `gemini-flash-lite-latest` was fast and reliable.
- Fix: default to `gemini-flash-lite-latest`, keep MODEL_ID overridable.
- Symptom B: the first real drill came back as a single-line "manifest" with keys
  run together (`apiVersion: v1 kind: Service ...`), which is not apply-able YAML.
- Root cause: the lite model collapsed the YAML onto one line inside the JSON string.
- Fix: prompt now demands real newlines with an explicit example, and the structural
  check rejects any manifest with fewer than three newlines (marks it unvalidated).
  Re-ran: got a proper 17-line static-pod drill with a failing livenessProbe.
- Note: true apply-validation (apply to a throwaway namespace, confirm it breaks) can
  only run on the local box, since the kind cluster is not reachable from the lambda.
  Still to be added there.

## Phase 2 — infra spine

### 2026-07-16 — Phase 2 done: spine deployed, nightly path proven with stubs

- Deployed two CDK stacks to us-east-1: the Dynamo table and the api stack (ingest
  lambda + keyed endpoint, reasoning lambda, EventBridge Scheduler at 03:00 Lagos).
- Proved it live: real rollup -> ingest (HTTP 200, 73 events) -> DynamoDB -> reasoning
  lambda -> brief written with focus_domain=troubleshooting, model_source=STUB ->
  stubbed delivery logged the full brief to CloudWatch. Full write-up in
  docs/runs/03-phase2-spine-deployed.md.
- The model and both delivery channels are stubbed and clearly labelled; nothing
  presents stub output as real.

### 2026-07-16 — two bugs the cloud run caught that local runs did not

- Symptom: reasoning lambda threw `unsupported operand type(s) for -: 'float' and
  'decimal.Decimal'`.
- Root cause: DynamoDB returns numbers as Decimal. The analysis mixed float exam
  weights with Decimal event counts read back from the table.
- Fix: cast event counts to int as they enter the weight math. Separately, add a
  `to_dynamo` helper so brief/drill writes (which carry floats) become Decimal, since
  put_item refuses float.
- Reasoning: these only surface against real DynamoDB, not the local pure-function
  tests. Worth the deploy-and-invoke loop to flush them out before Phase 3.

## Phase 1 — local data path

### 2026-07-16 — Phase 1 done: local data path proven end to end

- Built the topic map, the rollup parser, a mock ingest, and the nightly cron.
- Real data: today's rollup kept 73 resource events across 9 topics, every resource
  mapped, POSTed to the mock and got HTTP 200. Cron wrapper ran clean.
- Fixed a clarity issue mid-build: kubectl's non-resource calls (discovery, health)
  were inflating the count as `?` resource, so they are now counted separately as
  non_resource_requests, not mixed into the study signal.
- Full write-up: docs/runs/02-phase1-rollup-and-cron.md.
- Phase 1 boundary reached. Phase 2 is the CDK spine with a stubbed model call.

### 2026-07-16 — Step 1 done: audit logging on and proven

- Cluster recreated at v1.35.1 with audit logging on. Ran six real kubectl actions
  and confirmed 1183 structured JSON events, 98 from the human `kubernetes-admin`
  user, each carrying verb, objectRef.resource, user, timestamp, and stage.
- Full proof and the confirmed event schema: docs/runs/01-phase1-step1-audit-on.md.
- Kubeconfig for this cluster lives at `~/.kube-study.conf` (see snag A). The rollup
  reads via `docker exec`, so it does not depend on that.

### 2026-07-16 — a third snag: extraArgs schema is version-specific

- Symptom: recreate at v1.35.1 failed in kubeadm with `cannot unmarshal array into
  ... extraArgs of type map[string]string`.
- Root cause: kind emits kubeadm ClusterConfiguration as v1beta3 for v1.35.1, where
  extraArgs is a map. The v1beta4 list-of-{name,value} form (correct for v1.36+) is
  rejected. My earlier note had this backwards.
- Fix: used the map form for extraArgs. Documented the version split in the config
  comment so future me does not flip it again.
- Reasoning: the failure mode is loud (kubeadm refuses to init), so no silent drift,
  but it cost a recreate. Worth pinning the image and the schema together.

### 2026-07-16 — two snags on first cluster recreate

**Snag A: kubeconfig writes fail, cluster context empty.**
- Symptom: `kind create/delete` errors with `failed to lock config file: open
  /home/donaldraph/.kube/config.lock: permission denied`, and `kubectl config
  get-contexts` is empty.
- Root cause: `~/.kube/` is owned by `root:root` (mode 755), so the user cannot
  create `config` or `config.lock` inside it. This predates the project and is why
  the context was empty from the start.
- Fix: operator runs `sudo chown -R donaldraph:donaldraph ~/.kube` (needs a
  password this session does not have). Then recreate proceeds normally.
- Reasoning: fixing ownership repairs the whole kubectl workflow, not just this
  project. A repo-local KUBECONFIG override would have worked around it but left
  two competing kubeconfigs on a shared box, so the ownership fix is the honest one.

**Snag B: version drift on recreate.**
- Symptom: recreate pulled `kindest/node:v1.36.1`, not the v1.35.1 the old cluster
  and the exams use.
- Root cause: the first config did not pin a node image, so kind v0.32 used its
  newer default.
- Fix: pinned `image: kindest/node:v1.35.1` on the control-plane node in
  cluster/kind-config.yaml.
- Reasoning: exam parity matters more than newest; generated drills and command
  syntax must match v1.35.

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
