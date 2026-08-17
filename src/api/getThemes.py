import json

from src.services.themes import list_themes


def _response(status: int, body: dict | None = None):
    payload = {
        "statusCode": status,
        "status": "success" if 200 <= status < 300 else "error",
    }
    if body:
        payload.update(body)
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }


def lambda_handler(event, context=None):
    try:
        themes = list_themes()
        return _response(200, {"data": themes})
    except Exception:
        return _response(500, {"error": "internal_error"})
