"""The deterministic core: activity versus exam weight versus days-to-deadline.

Everything here is plain arithmetic, no model, no AWS. Given the recent daily
rollups and the per-skill last-practised state, it computes, per exam and domain,
how much of my actual activity went there versus how much its official weight says
should have, and how close each deadline is. The output is the structured analysis
the model reasons over. If you deleted the model, this still produces honest gap
numbers; what it cannot do is judge avoided-versus-mastered or write a drill.

Exam weights are configuration, kept in one place with their provenance. The CKS
split (20/20/20/15/15/10) is the current CNCF v1.34-v1.35 blueprint; older guides
circulate an outdated 10/15 for Cluster Setup / System Hardening. Verify against the
live CNCF curriculum before the exam. See docs for the sources.
"""
import datetime as dt

# exam -> (pass mark, deadline, {domain: weight}). Weights sum to 1.0 per exam.
EXAMS = {
    "CKA": {
        "pass": 0.66,
        "deadline": dt.date(2026, 11, 30),
        "weights": {
            "troubleshooting": 0.30,
            "cluster-architecture": 0.25,
            "services-networking": 0.20,
            "workloads-scheduling": 0.15,
            "storage": 0.10,
        },
    },
    "CKS": {
        "pass": 0.67,
        "deadline": dt.date(2027, 2, 28),
        "weights": {
            "microservice-vulnerabilities": 0.20,
            "supply-chain-security": 0.20,
            "runtime-security": 0.20,
            "cluster-setup": 0.15,
            "cluster-hardening": 0.15,
            "system-hardening": 0.10,
        },
    },
    "CKAD": {
        "pass": 0.66,
        "deadline": dt.date(2027, 4, 30),
        "weights": {
            "app-env-config-security": 0.25,
            "app-design-build": 0.20,
            "app-deployment": 0.20,
            "services-networking": 0.20,
            "app-observability": 0.15,
        },
    },
}

# How each rollup topic maps onto each exam's domains. Approximate by design: this
# is the deterministic ~70 percent. Topics with no meaningful home in an exam map
# to None and simply do not count toward that exam. Many CKS domains (system
# hardening, image scanning) have no API-observable topic at all, which is itself a
# finding the reasoning layer surfaces rather than hides.
TOPIC_TO_DOMAIN = {
    "CKA": {
        "pod-lifecycle": "workloads-scheduling",
        "workloads": "workloads-scheduling",
        "scheduling": "workloads-scheduling",
        "config": "workloads-scheduling",
        "services-networking": "services-networking",
        "networkpolicy": "services-networking",
        "storage": "storage",
        "rbac": "cluster-architecture",
        "pod-security": "cluster-architecture",
        "admission-control": "cluster-architecture",
        "cluster-security": "cluster-architecture",
        "cluster-admin": "cluster-architecture",
        "troubleshooting": "troubleshooting",
    },
    "CKS": {
        "pod-security": "microservice-vulnerabilities",
        "config": "microservice-vulnerabilities",
        "admission-control": "supply-chain-security",
        "troubleshooting": "runtime-security",
        "networkpolicy": "cluster-setup",
        "services-networking": "cluster-setup",
        "cluster-admin": "cluster-setup",
        "rbac": "cluster-hardening",
        "cluster-security": "cluster-hardening",
        # workloads, scheduling, storage, pod-lifecycle: no strong CKS home
    },
    "CKAD": {
        "pod-lifecycle": "app-design-build",
        "workloads": "app-deployment",
        "scheduling": "app-deployment",
        "services-networking": "services-networking",
        "networkpolicy": "services-networking",
        "config": "app-env-config-security",
        "storage": "app-env-config-security",
        "rbac": "app-env-config-security",
        "pod-security": "app-env-config-security",
        "troubleshooting": "app-observability",
        # cluster-admin, admission-control, cluster-security: not CKAD-shaped
    },
}

# Skills worth watching for decay: the observable skill topics plus the API-blind
# ones (which decay silently and must be nudged from their last known practise).
DECAY_WATCH = [
    "troubleshooting", "services-networking", "networkpolicy", "storage",
    "rbac", "workloads", "scheduling", "config", "pod-security",
    "etcd-backup-restore", "static-pods", "system-hardening",
]
DECAY_DAYS = 7  # a skill untouched this long is flagged as decaying


def days_to(deadline, today):
    return (deadline - today).days


def _urgency(days):
    """Nearer deadlines weigh more. Smooth, bounded in (0, 1]."""
    return 1.0 / (1.0 + max(days, 0) / 30.0)


def _window_topic_counts(rollups):
    counts = {}
    for r in rollups:
        for topic, n in (r.get("by_topic") or {}).items():
            counts[topic] = counts.get(topic, 0) + n
    return counts


def build_analysis(rollups, skill_state, today):
    """Return the structured analysis the model reasons over.

    rollups: recent daily rollup dicts (any order).
    skill_state: {skill_name: last_practised_iso_date_or_None}.
    today: datetime.date.
    """
    topic_counts = _window_topic_counts(rollups)

    domains = []
    for exam, cfg in EXAMS.items():
        days = days_to(cfg["deadline"], today)
        urgency = _urgency(days)
        mapping = TOPIC_TO_DOMAIN[exam]

        # Roll topic activity up into this exam's domains.
        domain_events = {d: 0 for d in cfg["weights"]}
        for topic, n in topic_counts.items():
            d = mapping.get(topic)
            if d is not None:
                domain_events[d] += n
        total = sum(domain_events.values())

        for domain, weight in cfg["weights"].items():
            events = domain_events[domain]
            share = (events / total) if total else 0.0
            gap = weight - share  # positive: under-touched for its weight
            score = max(gap, 0.0) * weight * urgency
            domains.append({
                "exam": exam,
                "domain": domain,
                "weight": round(weight, 3),
                "events": events,
                "share": round(share, 3),
                "expected_share": round(weight, 3),
                "gap": round(gap, 3),
                "days_to_exam": days,
                "avoidance_score": round(score, 5),
            })

    # Most avoided first, so downstream (and the stub) can take domains[0].
    domains.sort(key=lambda d: d["avoidance_score"], reverse=True)

    decayed = []
    for skill in DECAY_WATCH:
        last = skill_state.get(skill)
        if last:
            since = (today - dt.date.fromisoformat(last)).days
            if since >= DECAY_DAYS:
                decayed.append({"skill": skill, "last_practised": last, "days_since": since})
        else:
            decayed.append({"skill": skill, "last_practised": None, "days_since": None})
    decayed.sort(key=lambda s: (s["days_since"] is not None, s["days_since"] or 0), reverse=True)

    return {
        "date": today.isoformat(),
        "days_to_exam": {e: days_to(c["deadline"], today) for e, c in EXAMS.items()},
        "domains": domains,
        "decayed_skills": decayed,
        "yesterdays_drill": None,  # filled by the reasoning lambda if present
    }
