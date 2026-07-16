"""POST /ingest — receive one daily rollup from the local cron and store it.

The rollup is the compact JSON the local rollup.py builds from the audit log. This
handler is a dumb, idempotent writer: it validates the shape, stores the day's
rollup, and stamps each touched skill's last-practised date. It does no judgment.
The reasoning lambda derives decay and avoidance from the stored rollups later, so
re-posting the same day is safe (every write here is a plain SET, never an
increment).
"""
import json

from common import respond, TABLE, ROLLUP_PK, SKILL_PK


def _parse_body(event):
    body = event.get("body")
    if body is None:
        return None
    if isinstance(body, (dict, list)):
        return body
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def handler(event, context):
    rollup = _parse_body(event)
    if not isinstance(rollup, dict):
        return respond(400, {"error": "body must be a rollup JSON object"})

    date = rollup.get("date")
    if not date:
        return respond(400, {"error": "rollup is missing 'date'"})

    # Store the day's rollup under ROLLUP / <date>.
    item = {"PK": ROLLUP_PK, "SK": date, **rollup}
    TABLE.put_item(Item=item)

    # Stamp last-practised on each skill actually exercised. Idempotent SET, so a
    # re-post of the same day changes nothing. Chronological arrival (nightly cron)
    # means the newest post naturally holds the latest date.
    skills = rollup.get("skills_touched") or []
    for skill in skills:
        count = (rollup.get("by_topic") or {}).get(skill, 0)
        TABLE.update_item(
            Key={"PK": SKILL_PK, "SK": skill},
            UpdateExpression="SET last_practised = :d, last_count = :c",
            ExpressionAttributeValues={":d": date, ":c": count},
        )

    return respond(200, {
        "ok": True,
        "date": date,
        "stored_events": rollup.get("totals", {}).get("events_kept"),
        "skills_stamped": skills,
    })
