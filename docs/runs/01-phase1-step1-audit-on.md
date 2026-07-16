# Phase 1, Step 1 — API server audit logging is on and proven

Date: 2026-07-16

## Goal

Turn on API server audit logging in the local `study` kind cluster and confirm it
emits structured events I can map to exam domains. This is the riskiest part of
the whole project, so it goes first.

## What was done

- Recreated the `study` cluster from `cluster/kind-config.yaml`, pinned to
  `kindest/node:v1.35.1` (the exam version), with the audit policy in
  `audit/policy.yaml` mounted in and the API server pointed at it.
- Generated a little real study activity through kubectl: create namespace, run a
  pod, get pods, describe the pod, create a serviceaccount, list namespaces.
- Read the log back out of the control-plane container with `docker exec`.

## Result (real numbers from the run)

- Log present at `/var/log/kubernetes/kube-apiserver-audit.log`, 1183 events after
  a fresh cluster plus the six commands above.
- Every event is one JSON object with the fields the rollup needs:
  - `verb` (create, get, list, patch, ...)
  - `objectRef.resource`, `objectRef.namespace`, `objectRef.name`, `objectRef.apiVersion`
  - `user.username`
  - `requestReceivedTimestamp`
  - `stage` (ResponseComplete is present, so events can be deduped on that stage)
- The human study user is `kubernetes-admin` (98 events from the six commands).
  System components are their own usernames (`system:apiserver`,
  `system:kube-controller-manager`, `system:kube-scheduler`,
  `system:node:study-control-plane`, service accounts). The rollup filters to the
  human user in code, so the raw log stays honest.

Sample `kubernetes-admin` create event, trimmed to the fields that matter:

```json
{
  "verb": "create",
  "requestURI": "/api/v1/namespaces/default/serviceaccounts",
  "requestReceivedTimestamp": "2026-07-16T17:06:52.622448Z",
  "stage": "ResponseComplete",
  "user": "kubernetes-admin",
  "objectRef": {
    "resource": "serviceaccounts",
    "namespace": "default",
    "name": "studybot",
    "apiVersion": "v1"
  }
}
```

## Snags hit and fixed on the way (see BUILD_LOG.md for detail)

- `~/.kube` is owned by root on this shared box, so kind could not write the
  default kubeconfig. Worked around by writing this cluster's kubeconfig to a
  user-owned path (`~/.kube-study.conf`); the audit extraction uses `docker exec`
  and does not depend on kubeconfig location. The root ownership of `~/.kube` is a
  separate system issue still to be fixed for normal kubectl use.
- The `extraArgs` schema flipped between image versions: `v1.35.1` emits kubeadm
  `v1beta3` (extraArgs is a map), while `v1.36.1` uses `v1beta4` (a list). Pinned
  to v1.35.1 and used the map form.

## Boundary

This step proves the audit log is on and structured. Turning it into a compact
daily rollup and POSTing it is Step 2.
