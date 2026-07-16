"""GET /briefs?limit=N — recent briefs, newest first, for the trend view."""
from boto3.dynamodb.conditions import Key

from common import respond, TABLE, BRIEF_PK

MAX_LIMIT = 60


def handler(event, context):
    params = event.get("queryStringParameters") or {}
    try:
        limit = min(int(params.get("limit", 30)), MAX_LIMIT)
    except (TypeError, ValueError):
        limit = 30

    res = TABLE.query(
        KeyConditionExpression=Key("PK").eq(BRIEF_PK),
        ScanIndexForward=False,
        Limit=limit,
    )
    return respond(200, {"briefs": res.get("Items", [])})
