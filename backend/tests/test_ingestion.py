import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
import app.ingestion as ingestion


client = TestClient(app)


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def sample_log():
    return {
        "timestamp": "2026-08-01T10:00:00Z",
        "service": "test-inventory-service",
        "level": "ERROR",
        "message": "Inventory service unavailable",
    }


@pytest.fixture
def sample_metric():
    return {
        "name": "test_cpu_usage",
        "value": 75.5,
        "labels": {
            "service": "test-inventory-service",
        },
    }


@pytest.fixture
def sample_trace():
    return {
        "trace_id": "test-trace-001",
        "service": "test-inventory-service",
        "operation": "get_inventory",
        "timestamp": "2026-08-01T10:00:00Z",
        "attributes": {
            "http.method": "GET",
        },
    }


@pytest.fixture
def sample_alert():
    return {
        "alert_name": "TestMicroserviceDown",
        "service": "test-inventory-service",
        "severity": "critical",
        "status": "firing",
        "summary": "Test inventory service unavailable",
        "description": "Integration test alert",
    }


# ============================================================
# LOG INGESTION
# ============================================================

def test_ingest_valid_log(sample_log, tmp_path, monkeypatch):
    """
    Verify that a valid log is accepted and stored as JSONL.
    """

    monkeypatch.setattr(
        ingestion,
        "LOG_DIR",
        str(tmp_path),
    )

    response = client.post(
        "/api/ingest/logs",
        json=sample_log,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "accepted"
    assert body["type"] == "log"
    assert body["service"] == sample_log["service"]

    log_file = (
        tmp_path /
        f"{sample_log['service']}.jsonl"
    )

    assert log_file.exists()

    lines = log_file.read_text(
        encoding="utf-8"
    ).strip().splitlines()

    assert len(lines) == 1

    stored_log = json.loads(lines[0])

    assert stored_log["timestamp"] == sample_log["timestamp"]
    assert stored_log["service"] == sample_log["service"]
    assert stored_log["level"] == sample_log["level"]
    assert stored_log["message"] == sample_log["message"]


# ============================================================
# METRIC INGESTION
# ============================================================

def test_ingest_valid_metric(sample_metric, monkeypatch):
    """
    Verify that a valid metric is accepted and sent
    to Pushgateway.
    """

    class MockResponse:
        ok = True
        status_code = 200
        text = "OK"

    captured = {}

    def mock_post(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return MockResponse()

    monkeypatch.setattr(
        ingestion.requests,
        "post",
        mock_post,
    )

    response = client.post(
        "/api/ingest/metrics",
        json=sample_metric,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "accepted"
    assert body["type"] == "metric"
    assert body["name"] == sample_metric["name"]
    assert body["value"] == sample_metric["value"]

    assert captured["url"].endswith(
        "/metrics/job/unified-ingestion"
    )

    assert (
        captured["kwargs"]["headers"]["Content-Type"]
        == "text/plain"
    )

    metric_data = captured["kwargs"]["data"]

    assert sample_metric["name"] in metric_data
    assert "75.5" in metric_data
    assert (
        'service="test-inventory-service"'
        in metric_data
    )


# ============================================================
# TRACE INGESTION
# ============================================================

def test_ingest_valid_trace(sample_trace, monkeypatch):
    """
    Verify that a valid trace is accepted.
    """

    class MockTraceProvider:
        def force_flush(self):
            return True

    monkeypatch.setattr(
        ingestion,
        "trace_provider",
        MockTraceProvider(),
    )

    response = client.post(
        "/api/ingest/traces",
        json=sample_trace,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "accepted"
    assert body["type"] == "trace"
    assert body["trace_id"] == sample_trace["trace_id"]
    assert body["service"] == sample_trace["service"]


# ============================================================
# ALERT INGESTION
# ============================================================

def test_ingest_valid_alert(sample_alert, monkeypatch):
    """
    Verify that a valid alert is inserted into PostgreSQL.
    """

    executed = {}

    class MockCursor:
        def execute(self, query, params):
            executed["query"] = query
            executed["params"] = params

        def close(self):
            pass

    class MockConnection:
        def cursor(self):
            return MockCursor()

        def commit(self):
            executed["committed"] = True

        def rollback(self):
            executed["rolled_back"] = True

        def close(self):
            pass

    def mock_connect(**kwargs):
        executed["connection"] = kwargs
        return MockConnection()

    monkeypatch.setattr(
        ingestion.psycopg2,
        "connect",
        mock_connect,
    )

    response = client.post(
        "/api/ingest/alerts",
        json=sample_alert,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "accepted"
    assert body["type"] == "alert"
    assert body["service"] == sample_alert["service"]
    assert body["alert_name"] == sample_alert["alert_name"]

    assert executed["committed"] is True

    params = executed["params"]

    assert params[0] == sample_alert["alert_name"]
    assert params[1] == sample_alert["service"]
    assert params[2] == sample_alert["severity"]
    assert params[3] == sample_alert["status"]
    assert params[4] == sample_alert["summary"]
    assert params[5] == sample_alert["description"]


# ============================================================
# INVALID / INCOMPLETE PAYLOAD TESTS
# ============================================================

def test_log_missing_required_field():
    payload = {
        "service": "test-service",
        "level": "ERROR",
    }

    response = client.post(
        "/api/ingest/logs",
        json=payload,
    )

    assert response.status_code == 422


def test_metric_invalid_name():
    payload = {
        "name": "invalid metric name!",
        "value": 10.0,
        "labels": {},
    }

    response = client.post(
        "/api/ingest/metrics",
        json=payload,
    )

    assert response.status_code == 422


def test_trace_missing_required_field():
    payload = {
        "trace_id": "trace-001",
        "service": "test-service",
    }

    response = client.post(
        "/api/ingest/traces",
        json=payload,
    )

    assert response.status_code == 422


def test_alert_missing_required_field():
    payload = {
        "alert_name": "TestAlert",
        "service": "test-service",
        "severity": "critical",
        "status": "firing",
    }

    response = client.post(
        "/api/ingest/alerts",
        json=payload,
    )

    assert response.status_code == 422


def test_empty_log_payload():
    response = client.post(
        "/api/ingest/logs",
        json={},
    )

    assert response.status_code == 422


def test_empty_metric_payload():
    response = client.post(
        "/api/ingest/metrics",
        json={},
    )

    assert response.status_code == 422


def test_empty_trace_payload():
    response = client.post(
        "/api/ingest/traces",
        json={},
    )

    assert response.status_code == 422


def test_empty_alert_payload():
    response = client.post(
        "/api/ingest/alerts",
        json={},
    )

    assert response.status_code == 422