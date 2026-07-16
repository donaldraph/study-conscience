"""The nightly agent. Triggered ~03:00 by EventBridge Scheduler.

Reads the recent daily rollups and the per-skill state, computes the deterministic
avoidance analysis, hands it to the model seam for the judgment, drill, and grade,
then writes today's brief and today's drill back to the table. Delivery (Telegram,
email) is a later step; this lambda's job is to produce the brief.
"""
import datetime as dt
import os

from boto3.dynamodb.conditions import Key

import analysis
import delivery
import model
from common import (
    TABLE, ROLLUP_PK, SKILL_PK, DRILL_PK, BRIEF_PK, local_today, to_dynamo,
)

WINDOW_DAYS = int(os.environ.get("WINDOW_DAYS", "14"))


def _recent_rollups(limit):
    res = TABLE.query(
        KeyConditionExpression=Key("PK").eq(ROLLUP_PK),
        ScanIndexForward=False,  # newest dates first
        Limit=limit,
    )
    return res.get("Items", [])


def _skill_state():
    res = TABLE.query(KeyConditionExpression=Key("PK").eq(SKILL_PK))
    return {i["SK"]: i.get("last_practised") for i in res.get("Items", [])}


def _yesterdays_drill(today):
    y = (today - dt.timedelta(days=1)).isoformat()
    item = TABLE.get_item(Key={"PK": DRILL_PK, "SK": y}).get("Item")
    return item


def handler(event, context):
    today = local_today()

    rollups = _recent_rollups(WINDOW_DAYS)
    skills = _skill_state()

    an = analysis.build_analysis(rollups, skills, today)
    an["yesterdays_drill"] = _yesterdays_drill(today)

    out = model.run_model(an)

    # The brief keeps both the model's judgment and the deterministic panels, so the
    # dashboard can show the honest numbers next to the narrative.
    brief = {
        "PK": BRIEF_PK,
        "SK": today.isoformat(),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "model_source": out["source"],
        "avoidance_judgment": out["avoidance_judgment"],
        "focus_domain": out["focus_domain"],
        "drill": out["drill"],
        "grade": out["grade"],
        "days_to_exam": an["days_to_exam"],
        "top_avoided": an["domains"][:5],
        "domains": an["domains"],  # full exam x domain grid for the dashboard heatmap
        "decayed_skills": an["decayed_skills"][:5],
        "rollups_in_window": len(rollups),
    }
    TABLE.put_item(Item=to_dynamo(brief))

    # Persist today's drill so tomorrow's run can grade it.
    TABLE.put_item(Item=to_dynamo({
        "PK": DRILL_PK,
        "SK": today.isoformat(),
        "date": today.isoformat(),
        "model_source": out["source"],
        **out["drill"],
    }))

    # Hand the finished brief to delivery. Sends are stubbed, so this just logs the
    # formatted message to CloudWatch for now.
    delivery.deliver(brief)

    return {
        "date": today.isoformat(),
        "model_source": out["source"],
        "focus_domain": out["focus_domain"],
        "rollups_in_window": len(rollups),
    }
