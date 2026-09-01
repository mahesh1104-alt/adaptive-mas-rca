from app.log_preprocessing import (
    preprocess_log,
    normalize_level,
    normalize_timestamp,
    remove_obvious_pii,
    clean_stack_trace,
)


def test_parse_json_log():
    raw_log = {
        "timestamp": "2026-08-01T10:00:00Z",
        "service": "inventory-service",
        "level": "ERROR",
        "message": "Database connection failed",
        "error_code": "DB-001",
    }

    result = preprocess_log(raw_log)

    assert result["timestamp"] == "2026-08-01T10:00:00Z"
    assert result["service"] == "inventory-service"
    assert result["level"] == "ERROR"
    assert result["message"] == "Database connection failed"
    assert result["error_code"] == "DB-001"


def test_parse_plain_text_log():
    raw_log = (
        "2026-08-01T10:15:22Z "
        "ERROR "
        "service=inventory-service "
        "Database connection failed "
        "error_code=DB-001"
    )

    result = preprocess_log(raw_log)

    assert result["timestamp"] == "2026-08-01T10:15:22Z"
    assert result["service"] == "inventory-service"
    assert result["level"] == "ERROR"
    assert "Database connection failed" in result["message"]
    assert result["error_code"] == "DB-001"


def test_service_override():
    raw_log = {
        "level": "INFO",
        "message": "Inventory request completed",
    }

    result = preprocess_log(
        raw_log,
        service="inventory-service",
    )

    assert result["service"] == "inventory-service"


def test_level_normalization():
    assert normalize_level("warning") == "WARN"
    assert normalize_level("WARN") == "WARN"
    assert normalize_level("fatal") == "CRITICAL"
    assert normalize_level("ERROR") == "ERROR"


def test_timestamp_normalization():
    result = normalize_timestamp(
        "2026-08-01T10:00:00+00:00"
    )

    assert result == "2026-08-01T10:00:00Z"


def test_email_is_redacted():
    result = remove_obvious_pii(
        "User email is mahesh@example.com"
    )

    assert "mahesh@example.com" not in result
    assert "[REDACTED_EMAIL]" in result


def test_phone_is_redacted():
    result = remove_obvious_pii(
        "User phone is +91 98765 43210"
    )

    assert "+91 98765 43210" not in result
    assert "[REDACTED_PHONE]" in result


def test_stack_trace_boilerplate_is_removed():
    raw_log = """Traceback (most recent call last):
File "/app/service.py", line 42, in process
    connect_database()
ConnectionError: database unavailable"""

    result = clean_stack_trace(raw_log)

    assert "Traceback" not in result
    assert 'File "/app/service.py"' not in result
    assert "ConnectionError: database unavailable" in result


def test_error_code_extraction():
    raw_log = (
        "2026-08-01T10:00:00Z "
        "ERROR service=payment-service "
        "Payment failed [PAY-500]"
    )

    result = preprocess_log(raw_log)

    assert result["error_code"] == "PAY-500"


def test_missing_fields_get_safe_defaults():
    raw_log = {
        "message": "Something happened",
    }

    result = preprocess_log(raw_log)

    assert result["service"] == "unknown-service"
    assert result["level"] == "INFO"
    assert result["message"] == "Something happened"


def test_json_string_is_supported():
    raw_log = """
    {
        "timestamp": "2026-08-01T10:00:00Z",
        "service": "order-service",
        "level": "INFO",
        "message": "Order created"
    }
    """

    result = preprocess_log(raw_log)

    assert result["service"] == "order-service"
    assert result["level"] == "INFO"
    assert result["message"] == "Order created"