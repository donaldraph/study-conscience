"""Local daily rollup of the kind cluster's API server audit log.

Runs on this box, not in the cloud. It reads the audit log out of the control
plane container, keeps only the human study user's completed requests for one
local day, maps each to a canonical topic, and writes a compact daily rollup.

Raw audit logs never leave the box. Only the small rollup is shipped (POST step
lives in this same file, added next). Run:

    python3 -m rollup.rollup --date 2026-07-16 --out rollup/out/2026-07-16.json

or let it default to today's local date and print to stdout.
"""
import argparse
import collections
import datetime as dt
import json
import subprocess
import sys

from rollup import domain_map

DEFAULT_CONTAINER = "study-control-plane"
DEFAULT_LOG_PATH = "/var/log/kubernetes/kube-apiserver-audit.log"
DEFAULT_USER = "kubernetes-admin"
# Count an event once. ResponseComplete is the terminal stage for a served
# request; other stages (Panic, ResponseStarted) would double-count.
KEEP_STAGE = "ResponseComplete"


def extract_events(container, log_path, log_file):
    """Yield parsed audit events from the container, or from a local file."""
    if log_file:
        with open(log_file) as fh:
            lines = fh.readlines()
    else:
        out = subprocess.run(
            ["docker", "exec", container, "cat", log_path],
            capture_output=True, text=True, check=True,
        )
        lines = out.stdout.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            # A partial trailing line during active writes. Skip, do not crash.
            continue


def local_date_of(ts):
    """Convert an audit UTC timestamp to the box's local calendar date."""
    # Audit timestamps look like 2026-07-16T17:06:52.622448Z
    parsed = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return parsed.astimezone().date()


def local_minute_of(ts):
    parsed = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return parsed.astimezone().strftime("%Y-%m-%dT%H:%M")


def build_rollup(events, day, user):
    """Pure aggregation. Given events, return the compact daily rollup dict."""
    by_topic = collections.Counter()
    by_resource = collections.Counter()
    by_verb = collections.Counter()
    unmapped = collections.Counter()
    minutes = set()
    timestamps = []

    kept = 0
    non_resource = 0
    for evt in events:
        if evt.get("stage") != KEEP_STAGE:
            continue
        if (evt.get("user") or {}).get("username") != user:
            continue
        ts = evt.get("requestReceivedTimestamp")
        if not ts or local_date_of(ts) != day:
            continue

        obj = evt.get("objectRef") or {}
        resource = obj.get("resource")
        if not resource:
            # Non-resource request: discovery, /healthz, /version, openapi. Real
            # traffic but not study signal, so it is counted apart, not mapped.
            non_resource += 1
            minutes.add(local_minute_of(ts))
            continue

        kept += 1
        verb = evt.get("verb", "?")
        by_verb[verb] += 1
        by_resource[resource] += 1
        minutes.add(local_minute_of(ts))
        timestamps.append(ts)

        topic = domain_map.classify_event(evt)
        if topic is None:
            # A resource the map does not cover (not deliberate noise). Surface it
            # so coverage stays honest.
            if obj.get("subresource") != "status":
                unmapped[f"{verb} {resource}"] += 1
            continue
        by_topic[topic] += 1

    skills = sorted(t for t in by_topic if domain_map.is_skill(t) and by_topic[t] > 0)
    timestamps.sort()
    return {
        "date": day.isoformat(),
        "cluster": "study",
        "user": user,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "totals": {
            "events_kept": kept,
            "non_resource_requests": non_resource,
            "active_minutes": len(minutes),
            "first_activity": timestamps[0] if timestamps else None,
            "last_activity": timestamps[-1] if timestamps else None,
        },
        "by_topic": dict(by_topic.most_common()),
        "by_resource": dict(by_resource.most_common()),
        "by_verb": dict(by_verb.most_common()),
        "skills_touched": skills,
        "unmapped": dict(unmapped.most_common(10)),
        "unobservable_note": domain_map.UNOBSERVABLE,
    }


def parse_args(argv):
    p = argparse.ArgumentParser(description="Roll up the kind audit log for one day.")
    p.add_argument("--date", help="local date YYYY-MM-DD (default: today)")
    p.add_argument("--user", default=DEFAULT_USER, help="human study user in the audit log")
    p.add_argument("--container", default=DEFAULT_CONTAINER)
    p.add_argument("--log-path", default=DEFAULT_LOG_PATH)
    p.add_argument("--log-file", help="read a local log file instead of docker exec (for tests)")
    p.add_argument("--out", help="write the rollup JSON here (default: stdout)")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    day = (
        dt.date.fromisoformat(args.date) if args.date
        else dt.datetime.now().astimezone().date()
    )
    events = extract_events(args.container, args.log_path, args.log_file)
    rollup = build_rollup(events, day, args.user)
    text = json.dumps(rollup, indent=2)
    if args.out:
        import os
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w") as fh:
            fh.write(text + "\n")
        print(f"wrote {args.out}: {rollup['totals']['events_kept']} events, "
              f"{len(rollup['skills_touched'])} skills touched", file=sys.stderr)
    else:
        print(text)
    return rollup


if __name__ == "__main__":
    main()
