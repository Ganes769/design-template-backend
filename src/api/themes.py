import json

from pydantic import ValidationError

from src.models.theme import DesignThemeCreate
from src.services.themes import create_theme


def _response(status: int, body: dict):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def create(event, context):
    try:
        payload = json.loads(event.get("body") or "{}")
        theme = DesignThemeCreate.model_validate(payload)
        created = create_theme(theme)
        return _response(201, {"data": created})
    except json.JSONDecodeError:
        return _response(400, {"error": "invalid_json"})
    except ValidationError as exc:
        return _response(
            400,
            {"error": "validation_failed", "details": exc.errors()},
        )
    except ValueError as exc:
        return _response(409, {"error": str(exc)})
    except Exception as exc:
        return _response(500, {"error": str(exc)})
