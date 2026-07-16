"""Deterministic mapping from an audit event to a canonical study topic.

This is the honest 70 percent: a rules table that turns an API server verb plus
resource into one of a small set of canonical topics (the hands-on skill units).
The ambiguous residue and the avoidance judgment are the model's job in the
reasoning layer, not here.

Topics are exam-agnostic on purpose. Each topic rolls up to a CKA / CKS / CKAD
exam domain (with weights) in the reasoning layer, where the exam weightings and
days-to-deadline live. Keeping that split means this file never has to change when
an exam re-weights its blueprint.

Known blind spot: some exam-critical skills never appear in the API server audit
log because they are node-level shell work, not kubectl. etcd snapshot save and
restore, static pod placement in /etc/kubernetes/manifests, kubeadm upgrades, and
most CKS system hardening happen off the API. The reasoning layer must treat "no
audit evidence" for those as unknown, not as mastered. See UNOBSERVABLE below.
"""

# resource (objectRef.resource) -> canonical topic
RESOURCE_TOPIC = {
    # pods and their lifecycle
    "pods": "pod-lifecycle",
    # workloads and scheduling
    "deployments": "workloads",
    "replicasets": "workloads",
    "statefulsets": "workloads",
    "daemonsets": "workloads",
    "jobs": "workloads",
    "cronjobs": "workloads",
    "replicationcontrollers": "workloads",
    "horizontalpodautoscalers": "workloads",
    "priorityclasses": "scheduling",
    "nodes": "scheduling",
    # services and networking
    "services": "services-networking",
    "endpoints": "services-networking",
    "endpointslices": "services-networking",
    "ingresses": "services-networking",
    "ingressclasses": "services-networking",
    "networkpolicies": "networkpolicy",
    # storage
    "persistentvolumes": "storage",
    "persistentvolumeclaims": "storage",
    "storageclasses": "storage",
    "volumeattachments": "storage",
    "csidrivers": "storage",
    "csinodes": "storage",
    # config
    "configmaps": "config",
    "secrets": "config",
    # rbac and identity
    "roles": "rbac",
    "rolebindings": "rbac",
    "clusterroles": "rbac",
    "clusterrolebindings": "rbac",
    "serviceaccounts": "rbac",
    # security posture (CKS-heavy)
    "podsecuritypolicies": "pod-security",
    "securitycontextconstraints": "pod-security",
    "validatingwebhookconfigurations": "admission-control",
    "mutatingwebhookconfigurations": "admission-control",
    "validatingadmissionpolicies": "admission-control",
    "validatingadmissionpolicybindings": "admission-control",
    "certificatesigningrequests": "cluster-security",
    "resourcequotas": "cluster-admin",
    "limitranges": "cluster-admin",
    "namespaces": "cluster-admin",
    "componentstatuses": "cluster-admin",
    "events": "troubleshooting",
    "leases": "cluster-admin",
    "customresourcedefinitions": "cluster-admin",
}

# objectRef.subresource -> canonical topic (wins over the resource mapping)
SUBRESOURCE_TOPIC = {
    "log": "troubleshooting",
    "exec": "troubleshooting",
    "portforward": "troubleshooting",
    "status": None,          # status writes are controller noise, drop by default
    "scale": "workloads",
    "token": "rbac",
    "eviction": "troubleshooting",
    "attach": "troubleshooting",
}

# Topics that are real hands-on skills worth tracking for avoidance and decay.
# Everything else (discovery, cluster-admin bookkeeping) is context, not a skill.
SKILL_TOPICS = {
    "pod-lifecycle",
    "workloads",
    "scheduling",
    "services-networking",
    "networkpolicy",
    "storage",
    "config",
    "rbac",
    "pod-security",
    "admission-control",
    "cluster-security",
    "troubleshooting",
}

# Skills the API audit log cannot see. Listed so the reasoning layer knows these
# exist and must not be scored as mastered just because they never show up.
UNOBSERVABLE = [
    "etcd-backup-restore",
    "static-pods",
    "kubeadm-upgrade",
    "system-hardening",
    "kubelet-config",
    "image-scanning",
]


def classify_event(evt):
    """Return the canonical topic for one audit event, or None to drop it.

    None means the event is noise (a status subresource, or a resource we do not
    map). Callers should record dropped-but-not-noise events as unmapped so the
    map's coverage stays visible and honest.
    """
    obj = evt.get("objectRef") or {}
    sub = obj.get("subresource")
    if sub in SUBRESOURCE_TOPIC:
        return SUBRESOURCE_TOPIC[sub]
    resource = obj.get("resource")
    return RESOURCE_TOPIC.get(resource)


def is_skill(topic):
    return topic in SKILL_TOPICS
