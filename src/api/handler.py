import json

from src.db import get_db


def hello(event, context):
    db = get_db()
    ping = db.command("ping")

    body = {
        "message": "Go Serverless v4.0! Your function executed successfully!",
        "mongodb": "ok" if ping.get("ok") == 1 else "error",
    }

    return {"statusCode": 200, "body": json.dumps(body)}
