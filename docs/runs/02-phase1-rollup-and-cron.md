# Phase 1, Steps 2-4 — daily rollup, POST, and the nightly cron

Date: 2026-07-16

## Goal

Turn the raw audit log into a compact daily rollup, ship only the rollup (never the
raw log), and run it every night from cron. Prove the whole local data path with
real cluster data before any AWS exists.

## What was built

- `rollup/domain_map.py`: the deterministic resource-and-verb to canonical-topic
  map. Thirteen topics. Non-resource requests (discovery, health) and status
  subresources are dropped as noise. Skills that never touch the API (etcd
  backup/restore, static pods, kubeadm upgrade, system hardening) are listed as
  unobservable so the reasoning layer never scores them as mastered on silence.
- `rollup/rollup.py`: reads the audit log out of the container with `docker exec`,
  keeps only the human user's `ResponseComplete` events for one local day, maps
  each to a topic, and emits the compact daily JSON. Optionally POSTs it.
- `rollup/mock_ingest.py`: a throwaway local endpoint standing in for API Gateway,
  so the POST can be proven with no AWS.
- `rollup/run.sh` + crontab entry at 02:45 WAT: the nightly job. It rolls up
  yesterday (the day that just ended), writes the file, and POSTs only if an
  ingest URL is configured.

## Proof with real data

Today's rollup, built from the live audit log:

- 73 resource events kept, 25 non-resource requests counted apart.
- Topics touched: rbac 33, config 10, cluster-admin 9, scheduling 7, workloads 6,
  pod-lifecycle 4, storage 2, services-networking 1, troubleshooting 1.
- Every resource in the log mapped: `unmapped` was empty.
- POSTed to the mock ingest, got HTTP 200 back, payload saved locally.
- The cron wrapper ran clean end to end (rolling up an empty yesterday, since the
  cluster was recreated today, which is itself the honest expected result).

## Honesty notes

- On the day the cluster is created, the `kubernetes-admin` events include kind's
  own bootstrap traffic (CNI install, storage class, RBAC), not just my study. On a
  normal study day the cluster is already up, so all `kubernetes-admin` activity is
  genuinely mine. Creation-day rollups are the only ones that carry bootstrap.
- The rollup ships a small JSON only. The raw audit log never leaves the box, and
  `rollup/out/` is gitignored so no rollup or received payload is committed either.
- The topic map is the deterministic 70 percent. Mapping topics to per-exam domains
  with weights, and the avoidance judgment, are the reasoning layer's job in Phase 2
  and Phase 3, not this script.

## Boundary reached

The local data path is proven end to end with real data. Next is Phase 2: the CDK
spine (ingest Lambda, DynamoDB, reasoning Lambda with a stubbed model call, nightly
trigger, stubbed delivery). At that point the cron's ingest URL points at the real
API Gateway instead of the mock.
