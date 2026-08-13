import json

from src.db import get_db

COLLECTION = "themes"


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
    path_params = (event or {}).get("pathParameters") or {}
    slug = path_params.get("slug") or (event or {}).get("slug")

    if not slug:
        return _response(400, {"error": "missing_slug"})

    db = get_db()
    doc = db[COLLECTION].find_one({"_id": slug})
    if not doc:
        return _response(404, {"error": "theme_not_found"})

    doc = dict(doc)
    doc.pop("_id", None)
    return _response(200, {"data": doc})