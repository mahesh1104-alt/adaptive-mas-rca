import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def engineer(client):
    unique_id = uuid.uuid4().hex[:10]

    payload = {
        "username": f"api_test_{unique_id}",
        "email": f"api_test_{unique_id}@example.com",
        "password": "SecurePass123!",
        "role": "engineer",
    }

    response = client.post(
        "/api/auth/register",
        json=payload,
    )

    assert response.status_code == 201

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": payload["email"],
            "password": payload["password"],
        },
    )

    assert login_response.status_code == 200

    token_data = login_response.json()

    return {
        "user": response.json(),
        "token": token_data["access_token"],
    }


def auth_headers(engineer):
    return {
        "Authorization": f"Bearer {engineer['token']}"
    }


# ============================================================
# Health
# ============================================================

def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"
    assert data["service"] == "adaptive-mas-rca-backend"


# ============================================================
# Authentication
# ============================================================

def test_auth_status(client):
    response = client.get("/api/auth/")

    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_register_and_login(client):
    unique_id = uuid.uuid4().hex[:10]

    payload = {
        "username": f"integration_{unique_id}",
        "email": f"integration_{unique_id}@example.com",
        "password": "SecurePass123!",
        "role": "engineer",
    }

    register_response = client.post(
        "/api/auth/register",
        json=payload,
    )

    assert register_response.status_code == 201

    registered_user = register_response.json()

    assert registered_user["username"] == payload["username"]
    assert registered_user["email"] == payload["email"]
    assert registered_user["role"] == "engineer"
    assert "password_hash" not in registered_user

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": payload["email"],
            "password": payload["password"],
        },
    )

    assert login_response.status_code == 200

    token_data = login_response.json()

    assert token_data["access_token"]
    assert token_data["token_type"] == "bearer"
    assert token_data["user_id"] == registered_user["user_id"]


def test_duplicate_registration_returns_409(client):
    unique_id = uuid.uuid4().hex[:10]

    payload = {
        "username": f"duplicate_{unique_id}",
        "email": f"duplicate_{unique_id}@example.com",
        "password": "SecurePass123!",
        "role": "engineer",
    }

    first = client.post(
        "/api/auth/register",
        json=payload,
    )

    assert first.status_code == 201

    second = client.post(
        "/api/auth/register",
        json=payload,
    )

    assert second.status_code == 409


def test_invalid_login_returns_401(client):
    unique_id = uuid.uuid4().hex[:10]

    payload = {
        "username": f"login_test_{unique_id}",
        "email": f"login_test_{unique_id}@example.com",
        "password": "SecurePass123!",
        "role": "engineer",
    }

    register_response = client.post(
        "/api/auth/register",
        json=payload,
    )

    assert register_response.status_code == 201

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": payload["email"],
            "password": "WrongPassword123!",
        },
    )

    assert login_response.status_code == 401


# ============================================================
# Protected API
# ============================================================

def test_diagnosis_requires_authentication(client):
    response = client.post(
        "/api/diagnosis",
        json={
            "incident_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 401


def test_diagnosis_invalid_incident_returns_404(client, engineer):
    response = client.post(
        "/api/diagnosis",
        headers=auth_headers(engineer),
        json={
            "incident_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 404


def test_diagnosis_job_not_found_returns_404(client, engineer):
    response = client.get(
        f"/api/diagnosis/jobs/{uuid.uuid4()}",
        headers=auth_headers(engineer),
    )

    assert response.status_code == 404


def test_diagnosis_job_requires_authentication(client):
    response = client.get(
        f"/api/diagnosis/jobs/{uuid.uuid4()}",
    )

    assert response.status_code == 401


# ============================================================
# Incidents API
# ============================================================

def test_incident_crud_flow(client, engineer):
    user_id = engineer["user"]["user_id"]

    create_response = client.post(
        "/api/incidents",
        json={
            "user_id": user_id,
            "title": "API Integration Incident",
            "description": "Database connection failure during integration testing.",
            "severity": "high",
            "status": "open",
            "source": "integration-test",
        },
    )

    assert create_response.status_code == 201

    incident = create_response.json()

    incident_id = incident["incident_id"]

    assert incident["user_id"] == user_id
    assert incident["title"] == "API Integration Incident"
    assert incident["severity"] == "high"
    assert incident["status"] == "open"

    get_response = client.get(
        f"/api/incidents/{incident_id}",
    )

    assert get_response.status_code == 200

    fetched = get_response.json()

    assert fetched["incident_id"] == incident_id

    list_response = client.get("/api/incidents")

    assert list_response.status_code == 200

    incidents = list_response.json()

    assert isinstance(incidents, list)
    assert any(
        item["incident_id"] == incident_id
        for item in incidents
    )

    update_response = client.put(
        f"/api/incidents/{incident_id}",
        json={
            "status": "resolved",
        },
    )

    assert update_response.status_code == 200

    updated = update_response.json()

    assert updated["incident_id"] == incident_id
    assert updated["status"] == "resolved"


def test_incident_invalid_id_returns_404(client):
    response = client.get(
        f"/api/incidents/{uuid.uuid4()}",
    )

    assert response.status_code == 404


def test_incident_create_with_invalid_user_returns_404(client):
    response = client.post(
        "/api/incidents",
        json={
            "user_id": str(uuid.uuid4()),
            "title": "Invalid User Incident",
            "description": "This should fail.",
            "severity": "medium",
            "status": "open",
            "source": "integration-test",
        },
    )

    assert response.status_code == 404


def test_incident_validation_error_returns_422(client, engineer):
    response = client.post(
        "/api/incidents",
        json={
            "user_id": engineer["user"]["user_id"],
            "title": "Invalid Severity Incident",
            "description": "Invalid severity should be rejected.",
            "severity": "this-severity-is-way-too-long",
            "status": "open",
            "source": "integration-test",
        },
    )

    assert response.status_code == 422


# ============================================================
# Feedback API
# ============================================================

def test_feedback_requires_authentication(client):
    response = client.post(
        "/api/feedback/",
        json={
            "user_id": str(uuid.uuid4()),
            "output_id": str(uuid.uuid4()),
            "rating": 5,
            "comments": "Good diagnosis.",
            "is_correct": True,
        },
    )

    assert response.status_code == 401


def test_feedback_invalid_output_returns_404(client, engineer):
    response = client.post(
        "/api/feedback/",
        headers=auth_headers(engineer),
        json={
            "user_id": engineer["user"]["user_id"],
            "output_id": str(uuid.uuid4()),
            "rating": 5,
            "comments": "Invalid output test.",
            "is_correct": True,
        },
    )

    assert response.status_code == 404


def test_feedback_invalid_rating_returns_422(client, engineer):
    response = client.post(
        "/api/feedback/",
        headers=auth_headers(engineer),
        json={
            "user_id": engineer["user"]["user_id"],
            "output_id": str(uuid.uuid4()),
            "rating": 10,
            "comments": "Invalid rating test.",
            "is_correct": True,
        },
    )

    assert response.status_code == 422


# ============================================================
# Dashboard
# ============================================================

def test_dashboard_endpoint(client):
    response = client.get("/api/dashboard/")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"
    assert data["message"] == "Dashboard router is working"