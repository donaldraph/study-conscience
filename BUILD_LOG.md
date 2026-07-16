# Build log

Running journal at RUN-MD standard: symptom / root cause / fix / reasoning, in
real time. Newest entries at the top of each phase.

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
