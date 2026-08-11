import base64
import json
from email import message_from_bytes
from email.policy import default as email_policy
from urllib.parse import parse_qs

from pydantic import ValidationError

from src.models.theme import DesignThemeCreate
from src.services.themes import create_theme

NESTED_JSON_FIELDS = {"classes", "designProfile"}
JSON_WRAPPER_KEYS = ("data", "theme", "payload", "body", "json")

FORM_DATA_HINT = (
    "Postman: Body -> form-data -> add key 'data' (Text) with the full theme JSON string."
)


class InvalidFormDataError(ValueError):
    pass


def _response(status: int, body: dict):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _header(event: dict, name: str) -> str:
    headers = event.get("headers") or {}
    lower = {str(k).lower(): v for k, v in headers.items()}
    return lower.get(name.lower(), "") or ""


def _raw_body(event: dict) -> bytes:
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        return base64.b64decode(body)
    if isinstance(body, bytes):
        return body
    return body.encode("utf-8")


def _extract_json_object(text: str) -> dict | None:
    text = text.strip()
    if not text:
        return None

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None

    try:
        parsed = json.loads(text[start : end + 1])
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        return None

    return None


def _coerce_form_fields(fields: dict) -> dict:
    if not fields:
        raise InvalidFormDataError(FORM_DATA_HINT)

    for key in JSON_WRAPPER_KEYS:
        if key in fields and isinstance(fields[key], str):
            obj = _extract_json_object(fields[key])
            if obj:
                return obj

    if len(fields) == 1:
        only = next(iter(fields.values()))
        if isinstance(only, str):
            obj = _extract_json_object(only)
            if obj:
                return obj

    for value in fields.values():
        if isinstance(value, str):
            obj = _extract_json_object(value)
            if obj and "slug" in obj:
                return obj

    payload = {}
    for key, value in fields.items():
        if key in NESTED_JSON_FIELDS and isinstance(value, str):
            nested = _extract_json_object(value)
            payload[key] = nested if nested is not None else value
        else:
            payload[key] = value

    if "slug" not in payload:
        raise InvalidFormDataError(FORM_DATA_HINT)

    return payload


def _parse_urlencoded(body: bytes) -> dict:
    parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    fields = {key: values[0] if len(values) == 1 else values for key, values in parsed.items()}
    return _coerce_form_fields(fields)


def _parse_multipart(body: bytes, content_type: str) -> dict:
    message = message_from_bytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body,
        policy=email_policy,
    )
    fields = {}
    if not message.is_multipart():
        raise InvalidFormDataError(FORM_DATA_HINT)

    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            value = part.get_content()
        else:
            charset = part.get_content_charset() or "utf-8"
            value = payload.decode(charset, errors="replace")
        fields[name] = value

    if not fields:
        raise InvalidFormDataError(FORM_DATA_HINT)

    return _coerce_form_fields(fields)


def _parse_payload(event: dict) -> dict:
    content_type = _header(event, "content-type").lower()
    raw = _raw_body(event)

    if not raw.strip():
        return {}

    if "multipart/form-data" in content_type:
        return _parse_multipart(raw, _header(event, "content-type"))

    if "application/x-www-form-urlencoded" in content_type:
        return _parse_urlencoded(raw)

    if "application/json" in content_type or content_type == "":
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            if content_type == "":
                return _parse_urlencoded(raw)
            raise exc

    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return _parse_urlencoded(raw)


def create(event, context):
    try:
        payload = _parse_payload(event)
        if not isinstance(payload, dict):
            return _response(400, {"error": "invalid_payload", "hint": FORM_DATA_HINT})
        theme = DesignThemeCreate.model_validate(payload)
        created = create_theme(theme)
        return _response(201, {"data": created})
    except InvalidFormDataError as exc:
        return _response(400, {"error": "invalid_form_data", "hint": str(exc)})
    except json.JSONDecodeError:
        return _response(400, {"error": "invalid_json", "hint": FORM_DATA_HINT})
    except ValidationError as exc:
        return _response(
            400,
            {"error": "validation_failed", "details": exc.errors(), "hint": FORM_DATA_HINT},
        )
    except ValueError as exc:
        return _response(409, {"error": str(exc)})
    except Exception as exc:
        return _response(500, {"error": str(exc)})
