"""GET /brief — the latest brief, or ?date=YYYY-MM-DD for a specific day."""
from boto3.dynamodb.conditions import Key

from common import respond, TABLE, BRIEF_PK


def handler(event, context):
    params = event.get("queryStringParameters") or {}
    date = params.get("date")

    if date:
        item = TABLE.get_item(Key={"PK": BRIEF_PK, "SK": date}).get("Item")
    else:
        # Latest brief: newest SK first, take one.
        res = TABLE.query(
            KeyConditionExpression=Key("PK").eq(BRIEF_PK),
            ScanIndexForward=False,
            Limit=1,
        )
        items = res.get("Items", [])
        item = items[0] if items else None

    if not item:
        return respond(404, {"brief": None, "message": "no brief yet"})
    return respond(200, {"brief": item})
