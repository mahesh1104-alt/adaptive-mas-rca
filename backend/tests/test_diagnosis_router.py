import time
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.security import create_access_token


client = TestClient(app)

EXISTING_INCIDENT_ID = (
    "7a06545a-97bd-4a1c-80b3-717559dc169b"
)

ENGINEER_USER_ID = (
    "3efbc0ff-9246-48ab-9f37-b41f3f1c3cca"
)


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
    Verify that diagnosis is submitted as a background job
    for an existing incident.
    """

    response = client.post(
        "/api/diagnosis",
        json={
            "incident_id": EXISTING_INCIDENT_ID
        },
        headers=engineer_headers(),
    )

    # Background diagnosis must return immediately with 202.
    assert response.status_code == 202

    body = response.json()

    assert body["status"] == "accepted"
    assert body["job_id"]
    assert body["incident_id"] == EXISTING_INCIDENT_ID

    job_id = body["job_id"]

    # Verify that the job-status endpoint can retrieve the job.
    job_response = client.get(
        f"/api/diagnosis/jobs/{job_id}",
        headers=engineer_headers(),
    )

    assert job_response.status_code == 200

    job = job_response.json()

    assert job["job_id"] == job_id
    assert job["incident_id"] == EXISTING_INCIDENT_ID
    assert job["status"] in {
        "pending",
        "running",
        "completed",
        "failed",
    }

    # TestClient may execute FastAPI background tasks before
    # returning from the original request. If it has not completed,
    # poll the job endpoint for a short period.
    deadline = time.time() + 120

    while job["status"] in {"pending", "running"}:
        assert time.time() < deadline, (
            "Diagnosis background job did not finish within "
            "the expected time."
        )

        time.sleep(1)

        job_response = client.get(
            f"/api/diagnosis/jobs/{job_id}",
            headers=engineer_headers(),
        )

        assert job_response.status_code == 200

        job = job_response.json()

    # The background task must eventually complete successfully.
    assert job["status"] == "completed", (
        f"Diagnosis background job failed: {job.get('error')}"
    )

    assert job["report"] is not None
    assert isinstance(job["report"], dict)

    assert job["agent_outputs"] is not None
    assert isinstance(job["agent_outputs"], dict)

    expected_agents = {
        "log_analysis_agent",
        "metrics_analysis_agent",
        "source_code_analysis_agent",
        "trace_analysis_agent",
        "knowledge_retrieval_agent",
        "reasoning_agent",
        "validation_agent",
    }

    assert expected_agents.issubset(
        job["agent_outputs"].keys()
    )


def test_diagnosis_invalid_incident():
    """
    Verify that an unknown incident ID still returns 404
    before a background job is created.
    """

    response = client.post(
        "/api/diagnosis",
        json={
            "incident_id": str(
                uuid.uuid4()
            )
        },
        headers=engineer_headers(),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Incident not found"


def test_diagnosis_job_not_found():
    """
    Verify that an unknown diagnosis job ID returns 404.
    """

    response = client.get(
        f"/api/diagnosis/jobs/{uuid.uuid4()}",
        headers=engineer_headers(),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Diagnosis job not found"