import pytest

from app.embedding_generation import (
    generate_embedding,
    feature_bundle_to_text,
    generate_incident_embedding,
    historical_incident_to_text,
    generate_historical_incident_embedding,
)


def test_generate_embedding():
    text = "Database connection failed."

    embedding = generate_embedding(text)

    assert isinstance(embedding, list)
    assert len(embedding) == 384
    assert all(isinstance(value, float) for value in embedding)


def test_generate_embedding_rejects_non_string():
    with pytest.raises(TypeError):
        generate_embedding(123)


def test_generate_embedding_rejects_empty_text():
    with pytest.raises(ValueError):
        generate_embedding("")


def test_feature_bundle_to_text():
    feature_bundle = {
        "incident_id": "INC-TEST",
        "features": {
            "logs": [
                {
                    "level": "ERROR",
                    "template": "Database connection failed",
                }
            ],
            "metrics": [
                {
                    "metric": "cpu_usage",
                    "value": 95.0,
                    "unit": "%",
                    "anomaly": True,
                }
            ],
            "traces": [
                {
                    "trace_id": "trace-001",
                    "error_spans": [
                        {
                            "service": "inventory-service",
                            "operation": "update_stock",
                            "duration_ms": 200,
                        }
                    ],
                    "slow_spans": [],
                }
            ],
            "source": [
                {
                    "name": "update_stock",
                    "summary": "Update inventory quantity.",
                    "code": "stock -= quantity",
                }
            ],
        },
    }

    text = feature_bundle_to_text(feature_bundle)

    assert "INC-TEST" in text
    assert "Database connection failed" in text
    assert "cpu_usage" in text
    assert "inventory-service" in text
    assert "update_stock" in text


def test_generate_incident_embedding():
    feature_bundle = {
        "incident_id": "INC-TEST",
        "features": {
            "logs": [],
            "metrics": [],
            "traces": [],
            "source": [],
        },
    }

    embedding = generate_incident_embedding(feature_bundle)

    assert isinstance(embedding, list)
    assert len(embedding) == 384


def test_historical_incident_to_text():
    incident = {
        "incident_id": "INC-005",
        "alert_name": "DatabaseConnectionFailure",
        "service": "order-service",
        "severity": "critical",
        "summary": "Order service unable to connect to database",
        "description": "Database connection attempts were failing.",
        "root_cause": "Database connection pool was exhausted.",
        "resolution": "Increased connection pool limits.",
    }

    text = historical_incident_to_text(incident)

    assert "DatabaseConnectionFailure" in text
    assert "order-service" in text
    assert "critical" in text
    assert "Order service unable to connect to database" in text

    # Root cause and resolution must not be embedded.
    assert "Database connection pool was exhausted" not in text
    assert "Increased connection pool limits" not in text


def test_generate_historical_incident_embedding():
    incident = {
        "incident_id": "INC-005",
        "alert_name": "DatabaseConnectionFailure",
        "service": "order-service",
        "severity": "critical",
        "summary": "Order service unable to connect to database",
        "description": "Database connection attempts were failing.",
        "root_cause": "Database connection pool was exhausted.",
        "resolution": "Increased connection pool limits.",
    }

    embedding = generate_historical_incident_embedding(incident)

    assert isinstance(embedding, list)
    assert len(embedding) == 384