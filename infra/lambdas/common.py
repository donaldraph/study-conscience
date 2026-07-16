"""Shared helpers for every Lambda. Keeps the handlers small and consistent."""
import datetime
import decimal
import json
import os

import boto3

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover — stdlib on 3.9+
    ZoneInfo = None

_dynamodb = boto3.resource("dynamodb")
TABLE = _dynamodb.Table(os.environ["TABLE_NAME"])

CORS_HEADERS = {
    "Access-Control-Allow-Origin": os.environ.get("ALLOWED_ORIGIN", "*"),
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}

# Typed partitions in the single table. See data-stack.ts for the full layout.
ROLLUP_PK = "ROLLUP"   # SK = YYYY-MM-DD, a day's activity rollup
SKILL_PK = "SKILL"     # SK = skill name, per-skill state
DRILL_PK = "DRILL"     # SK = YYYY-MM-DD, the drill and its grade
BRIEF_PK = "BRIEF"     # SK = YYYY-MM-DD, the morning brief


def app_tz():
    """The timezone whose day-boundaries define 'today' and 'yesterday'.

    Prefers IANA data via zoneinfo; falls back to a fixed offset (default +1,
    correct for Lagos, which observes no DST) if the image lacks tzdata.
    Override the zone with APP_TZ, the fallback offset with APP_UTC_OFFSET_HOURS.
    """
    name = os.environ.get("APP_TZ", "Africa/Lagos")
    if ZoneInfo is not None:
        try:
            return ZoneInfo(name)
        except Exception:  # noqa: BLE001 — missing tzdata -> fixed-offset fallback
            pass
    offset = float(os.environ.get("APP_UTC_OFFSET_HOURS", "1"))
    return datetime.timezone(datetime.timedelta(hours=offset))


def local_now():
    return datetime.datetime.now(app_tz())


def local_today():
    return local_now().date()


def respond(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", **CORS_HEADERS},
        "body": json.dumps(body, default=str),
    }


def to_dynamo(obj):
    """Make a dict safe to put_item: DynamoDB rejects float, wants Decimal.

    Round-trips through JSON so every float becomes a Decimal in one shot. Cheap,
    and it keeps the handlers from sprinkling Decimal() everywhere.
    """
    return json.loads(json.dumps(obj, default=str), parse_float=decimal.Decimal)


def get_secret(name):
    """Fetch and JSON-parse a Secrets Manager secret by name."""
    client = boto3.client("secretsmanager")
    raw = client.get_secret_value(SecretId=name)["SecretString"]
    return json.loads(raw)
