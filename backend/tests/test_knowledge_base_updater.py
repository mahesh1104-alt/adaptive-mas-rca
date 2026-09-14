from unittest.mock import MagicMock, patch

import pytest

from app.knowledge_base_updater import add_resolved_incident


SAMPLE_INCIDENT = {
    "incident_id": "INC-031",
    "alert_name": "DatabaseConnectionFailure",
    "service": "order-service",
    "severity": "critical",
    "status": "resolved",
    "started_at": "2026-09-14T10:00:00",
    "resolved_at": "2026-09-14T10:15:00",
    "summary": "Order service unable to connect to database",
    "description": (
        "Database connection attempts from order service were failing."
    ),
    "root_cause": "Database connection pool was exhausted.",
    "resolution": "Increased database connection pool capacity.",
}


@patch("app.knowledge_base_updater.GraphDatabase.driver")
@patch(
    "app.knowledge_base_updater.store_historical_incident"
)
@patch(
    "app.knowledge_base_updater.generate_historical_incident_embedding"
)
@patch(
    "app.knowledge_base_updater.historical_incident_to_text"
)
def test_add_resolved_incident(
    mock_to_text,
    mock_embedding,
    mock_store,
    mock_driver,
):
    mock_to_text.return_value = (
        "DatabaseConnectionFailure order-service "
        "Database connection pool was exhausted."
    )

    mock_embedding.return_value = [0.1, 0.2, 0.3]

    driver = MagicMock()
    session = MagicMock()

    driver.session.return_value.__enter__.return_value = session
    mock_driver.return_value = driver

    result = add_resolved_incident(
        SAMPLE_INCIDENT
    )

    assert result["incident_id"] == "INC-031"
    assert result["chroma_updated"] is True
    assert result["neo4j_updated"] is True

    mock_to_text.assert_called_once_with(
        SAMPLE_INCIDENT
    )

    mock_embedding.assert_called_once_with(
        SAMPLE_INCIDENT
    )

    mock_store.assert_called_once_with(
        incident=SAMPLE_INCIDENT,
        embedding=[0.1, 0.2, 0.3],
        document=mock_to_text.return_value,
    )

    driver.verify_connectivity.assert_called_once()
    session.execute_write.assert_called_once()


def test_missing_incident_id():
    incident = SAMPLE_INCIDENT.copy()
    incident.pop("incident_id")

    with pytest.raises(ValueError):
        add_resolved_incident(incident)


def test_missing_root_cause():
    incident = SAMPLE_INCIDENT.copy()
    incident.pop("root_cause")

    with pytest.raises(ValueError):
        add_resolved_incident(incident)


def test_invalid_incident_type():
    with pytest.raises(TypeError):
        add_resolved_incident("not a dictionary")