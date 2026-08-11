import base64
import json
import re
from email import message_from_bytes
from email.policy import default as email_policy
from urllib.parse import parse_qs

from pydantic import ValidationError

from src.models.theme import DesignThemeCreate
from src.services.themes import create_theme

JSON_WRAPPER_KEYS = ("data", "theme", "payload", "body", "json")


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


def _unwrap_payload(payload: dict) -> dict:
    if not isinstance(payload, dict) or "slug" in payload:
        return payload
    for key in JSON_WRAPPER_KEYS:
        nested = payload.get(key)
        if isinstance(nested, dict) and "slug" in nested:
            return nested
    return payload


def _looks_like_theme(payload: dict) -> bool:
    if not isinstance(payload, dict):
        return False
    if "slug" in payload:
        return True
    return any(
        isinstance(payload.get(key), dict) and "slug" in payload[key]
        for key in JSON_WRAPPER_KEYS
    )


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
    text = (text or "").strip().lstrip("\ufeff")
    if not text:
        return None

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Find all candidate objects containing "slug"
    for match in re.finditer(r"\{", text):
        start = match.start()
        depth = 0
        for index in range(start, len(text)):
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    chunk = text[start : index + 1]
                    if '"slug"' not in chunk and "'slug'" not in chunk:
                        break
                    try:
                        parsed = json.loads(chunk)
                    except json.JSONDecodeError:
                        break
                    if isinstance(parsed, dict) and _looks_like_theme(parsed):
                        return parsed
                    break
    return None


def _normalize_fields(fields: dict) -> dict:
    return {
        str(key): (
            value.decode("utf-8", errors="replace")
            if isinstance(value, bytes)
            else str(value)
        )
        for key, value in fields.items()
    }


def _payload_from_fields(fields: dict) -> dict | None:
    if not fields:
        return None

    normalized = _normalize_fields(fields)

    for key in JSON_WRAPPER_KEYS:
        if key in normalized:
            obj = _extract_json_object(normalized[key])
            if obj and _looks_like_theme(obj):
                return _unwrap_payload(obj)

    for value in normalized.values():
        obj = _extract_json_object(value)
        if obj and _looks_like_theme(obj):
            return _unwrap_payload(obj)


    rebuilt_parts = []
    for key, value in normalized.items():
        rebuilt_parts.append(key)
        if value:
            rebuilt_parts.append(value)
    rebuilt = "\n".join(rebuilt_parts)
    obj = _extract_json_object(rebuilt)
    if obj and _looks_like_theme(obj):
        return _unwrap_payload(obj)

    joined = "\n".join(normalized.values())
    obj = _extract_json_object(joined)
    if obj and _looks_like_theme(obj):
        return _unwrap_payload(obj)

    if "slug" in normalized:
        return _unwrap_payload(normalized)

    return None


def _fields_from_multipart_email(body: bytes, content_type: str) -> dict:
    message = message_from_bytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
        + body,
        policy=email_policy,
    )
    fields = {}
    if not message.is_multipart():
        return fields

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
        fields[str(name)] = value if isinstance(value, str) else str(value)
    return fields


def _parse_boundary(content_type: str) -> str | None:
    match = re.search(r"boundary=(.+)$", content_type, flags=re.IGNORECASE)
    if not match:
        return None
    boundary = match.group(1).strip()
    if boundary.startswith('"') and boundary.endswith('"'):
        boundary = boundary[1:-1]
    return boundary


def _fields_from_multipart_manual(body: bytes, content_type: str) -> dict:
    boundary = _parse_boundary(content_type)
    if not boundary:
        return {}

    delimiter = f"--{boundary}".encode("utf-8")
    fields = {}
    for part in body.split(delimiter):
        chunk = part.strip(b"\r\n-")
        if not chunk:
            continue
        header_block, _, content = chunk.partition(b"\r\n\r\n")
        if not content:
            continue
        content = content.rstrip(b"\r\n")
        headers = header_block.decode("utf-8", errors="replace")
        name_match = re.search(r'name="([^"]+)"', headers, flags=re.IGNORECASE)
        if not name_match:
            name_match = re.search(r"name=([^;\r\n]+)", headers, flags=re.IGNORECASE)
        if not name_match:
            continue
        name = name_match.group(1).strip().strip('"')
        fields[name] = content.decode("utf-8", errors="replace")
    return fields


def _parse_multipart(body: bytes, content_type: str) -> dict | None:
    # Prefer scanning full body first — survives Postman bulk-edit mistakes
    text = body.decode("utf-8", errors="replace")
    payload = _extract_json_object(text)
    if payload and _looks_like_theme(payload):
        return _unwrap_payload(payload)

    fields = _fields_from_multipart_email(body, content_type)
    if not fields:
        fields = _fields_from_multipart_manual(body, content_type)

    return _payload_from_fields(fields)


def _parse_urlencoded(body: bytes) -> dict | None:
    text = body.decode("utf-8", errors="replace")
    payload = _extract_json_object(text)
    if payload and _looks_like_theme(payload):
        return _unwrap_payload(payload)

    parsed = parse_qs(text, keep_blank_values=True)
    fields = {key: values[0] if len(values) == 1 else values for key, values in parsed.items()}
    return _payload_from_fields(fields)


def _parse_payload(event: dict) -> dict | None:
    content_type = _header(event, "content-type").lower()
    raw = _raw_body(event)
    if not raw.strip():
        return None

    text = raw.decode("utf-8", errors="replace")

    if "multipart/form-data" in content_type:
        return _parse_multipart(raw, _header(event, "content-type"))

    if "application/x-www-form-urlencoded" in content_type:
        return _parse_urlencoded(raw)

    # JSON / unknown: parse directly, then recover from body text
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    payload = _extract_json_object(text)
    if payload is not None:
        return payload

    if content_type == "":
        return _parse_urlencoded(raw)
    return None


def create(event, context):
    try:
        parsed = _parse_payload(event)
        payload = _unwrap_payload(parsed) if isinstance(parsed, dict) else None
        if not isinstance(payload, dict) or not _looks_like_theme(payload):
            return _response(400, {"error": "invalid_payload"})

        theme = DesignThemeCreate.model_validate(payload)
        created = create_theme(theme)
        return _response(201, {"data": created})
    except ValidationError:
        return _response(400, {"error": "validation_failed"})
    except ValueError as exc:
        return _response(409, {"error": str(exc)})
    except Exception:
        return _response(500, {"error": "internal_error"})
