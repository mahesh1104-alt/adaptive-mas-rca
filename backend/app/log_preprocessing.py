import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional


# ============================================================
# REGULAR EXPRESSIONS
# ============================================================

EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)"
)

CREDIT_CARD_RE = re.compile(
    r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"
)

TIMESTAMP_RE = re.compile(
    r"""
    \b
    (
        \d{4}-\d{2}-\d{2}
        [T\s]
        \d{2}:\d{2}:\d{2}
        (?:\.\d+)?
        (?:Z|[+-]\d{2}:?\d{2})?
    )
    \b
    """,
    re.VERBOSE,
)

LEVEL_RE = re.compile(
    r"\b(DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL|FATAL)\b",
    re.IGNORECASE,
)

SERVICE_RE = re.compile(
    r"\bservice[=:]\s*[\"']?([A-Za-z0-9_.:/-]+)",
    re.IGNORECASE,
)

ERROR_CODE_RE = re.compile(
    r"\b(?:error[_ -]?code|code|err(?:or)?)[=:]\s*"
    r"[\"']?([A-Za-z0-9_.-]+)",
    re.IGNORECASE,
)


# ============================================================
# NORMALIZATION HELPERS
# ============================================================

def normalize_level(level: Optional[str]) -> str:
    """
    Normalize different log-level spellings into a standard form.
    """

    if not level:
        return "INFO"

    normalized = level.strip().upper()

    if normalized == "WARNING":
        return "WARN"

    if normalized == "FATAL":
        return "CRITICAL"

    if normalized not in {
        "DEBUG",
        "INFO",
        "WARN",
        "ERROR",
        "CRITICAL",
    }:
        return "INFO"

    return normalized


def normalize_timestamp(
    timestamp: Optional[str],
) -> Optional[str]:
    """
    Convert supported timestamp formats into UTC ISO-8601.
    """

    if not timestamp:
        return None

    value = str(timestamp).strip()

    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"

        parsed = datetime.fromisoformat(value)

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        parsed = parsed.astimezone(timezone.utc)

        return parsed.isoformat().replace(
            "+00:00",
            "Z",
        )

    except ValueError:
        return timestamp.strip()


def remove_obvious_pii(text: str) -> str:
    """
    Remove or mask obvious PII commonly found in logs.
    """

    text = EMAIL_RE.sub(
        "[REDACTED_EMAIL]",
        text,
    )

    text = PHONE_RE.sub(
        "[REDACTED_PHONE]",
        text,
    )

    text = CREDIT_CARD_RE.sub(
        "[REDACTED_CARD]",
        text,
    )

    return text


def clean_stack_trace(text: str) -> str:
    """
    Remove common stack-trace boilerplate while retaining
    useful exception information.
    """

    lines = text.splitlines()

    cleaned = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            continue

        if stripped.startswith("Traceback (most recent call last):"):
            continue

        if stripped.startswith("File \""):
            continue

        if stripped.startswith("^"):
            continue

        if stripped.startswith("During handling of the above exception"):
            continue

        if stripped.startswith("The above exception was the direct cause"):
            continue

        cleaned.append(stripped)

    return " ".join(cleaned)


def clean_message(message: str) -> str:
    """
    Apply common log-message cleanup.
    """

    message = str(message).strip()

    message = clean_stack_trace(message)

    message = remove_obvious_pii(message)

    message = re.sub(
        r"\s+",
        " ",
        message,
    ).strip()

    return message


# ============================================================
# FIELD EXTRACTION
# ============================================================

def extract_level(text: str) -> str:
    match = LEVEL_RE.search(text)

    if not match:
        return "INFO"

    return normalize_level(match.group(1))


def extract_service(text: str) -> Optional[str]:
    match = SERVICE_RE.search(text)

    if match:
        return match.group(1)

    return None


def extract_error_code(text: str) -> Optional[str]:
    match = ERROR_CODE_RE.search(text)

    if match:
        return match.group(1)

    # Also support common formats such as:
    # [DB-001]
    # (ERR-500)
    bracket_match = re.search(
        r"[\[(]([A-Z]{2,10}-\d{2,6})[\])]",
        text,
    )

    if bracket_match:
        return bracket_match.group(1)

    return None


def extract_timestamp(text: str) -> Optional[str]:
    match = TIMESTAMP_RE.search(text)

    if not match:
        return None

    return normalize_timestamp(match.group(1))


# ============================================================
# JSON LOG PARSING
# ============================================================

def parse_json_log(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a JSON log into the common schema.
    """

    timestamp = (
        payload.get("timestamp")
        or payload.get("time")
        or payload.get("@timestamp")
    )

    service = (
        payload.get("service")
        or payload.get("service_name")
        or payload.get("serviceName")
    )

    level = (
        payload.get("level")
        or payload.get("severity")
        or payload.get("log_level")
    )

    message = (
        payload.get("message")
        or payload.get("msg")
        or ""
    )

    error_code = (
        payload.get("error_code")
        or payload.get("errorCode")
    )

    result = {
        "timestamp": normalize_timestamp(
            str(timestamp)
        ) if timestamp else None,

        "service": str(service).strip()
        if service
        else None,

        "level": normalize_level(
            str(level)
        ) if level
        else "INFO",

        "message": clean_message(
            str(message)
        ),

        "error_code": str(error_code).strip()
        if error_code
        else None,
    }

    if not result["error_code"]:
        result["error_code"] = extract_error_code(
            result["message"]
        )

    return result


# ============================================================
# PLAIN TEXT LOG PARSING
# ============================================================

def parse_text_log(
    raw_log: str,
    service: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Parse a plain-text log into the common schema.
    """

    raw_log = str(raw_log).strip()

    timestamp = extract_timestamp(raw_log)

    level = extract_level(raw_log)

    detected_service = service or extract_service(
        raw_log
    )

    error_code = extract_error_code(
        raw_log
    )

    message = raw_log

    if timestamp:
        message = TIMESTAMP_RE.sub(
            "",
            message,
            count=1,
        )

    message = LEVEL_RE.sub(
        "",
        message,
        count=1,
    )

    if detected_service:
        message = SERVICE_RE.sub(
            "",
            message,
            count=1,
        )

    message = clean_message(message)

    return {
        "timestamp": timestamp,
        "service": detected_service,
        "level": level,
        "message": message,
        "error_code": error_code,
    }


# ============================================================
# UNIFIED LOG PARSER
# ============================================================

def preprocess_log(
    raw_log: Any,
    service: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convert JSON or plain-text logs into one common schema.

    Output schema:

    {
        "timestamp": "...",
        "service": "...",
        "level": "...",
        "message": "...",
        "error_code": "..."
    }
    """

    if isinstance(raw_log, dict):
        result = parse_json_log(raw_log)

    elif isinstance(raw_log, str):
        stripped = raw_log.strip()

        try:
            parsed = json.loads(stripped)

            if isinstance(parsed, dict):
                result = parse_json_log(parsed)
            else:
                result = parse_text_log(
                    stripped,
                    service=service,
                )

        except json.JSONDecodeError:
            result = parse_text_log(
                stripped,
                service=service,
            )

    else:
        raise TypeError(
            "raw_log must be a dictionary or string"
        )

    if service:
        result["service"] = service

    result["service"] = (
        result["service"]
        or "unknown-service"
    )

    return result