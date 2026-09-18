import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.security import create_access_token


client = TestClient(app)

EXISTING_INCIDENT_ID = "7a06545a-97bd-4a1c-80b3-717559dc169b"
ENGINEER_USER_ID = "3efbc0ff-9246-48ab-9f37-b41f3f1c3cca"


def engineer_headers():
    token = create_access_token(
        user_id=uuid.UUID(ENGINEER_USER_ID),
        username="mahesh",
        role="engineer",
    )
    return {
        "Authorization": f"Bearer {token}"
    }


def test_diagnosis_existing_incident():
    """
    Verify that diagnosis can be executed for an existing incident
    and that the response contains the final report and all agent outputs.
    """
    response = client.post(
        "/api/diagnosis",
        json={
            "incident_id": EXISTING_INCIDENT_ID
        },
        headers=engineer_headers(),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "success"
    assert body["incident_id"] == EXISTING_INCIDENT_ID

    # Final diagnosis report
    assert "report" in body
    assert isinstance(body["report"], dict)
    assert "root_cause" in body["report"]
    assert "confidence" in body["report"]

    # LangGraph agent outputs
    assert "agent_outputs" in body
    assert isinstance(body["agent_outputs"], dict)

    expected_agents = {
        "log_analysis_agent",
        "metrics_analysis_agent",
        "source_code_analysis_agent",
        "trace_analysis_agent",
        "knowledge_retrieval_agent",
        "reasoning_agent",
        "validation_agent",
    }

    assert expected_agents.issubset(body["agent_outputs"].keys())


def test_diagnosis_invalid_incident():
    """
    Verify that diagnosis returns 404 for an incident that does not exist.
    """
    missing_incident_id = str(uuid.uuid4())

    response = client.post(
        "/api/diagnosis",
        json={
            "incident_id": missing_incident_id
        },
        headers=engineer_headers(),
    )

    assert response.status_code == 404