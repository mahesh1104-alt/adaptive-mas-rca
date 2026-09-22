import uuid

from datetime import datetime

from app.db.models import Feedback
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import SessionLocal
from app.db.models import User, Incident, AgentOutput
from app.security import create_access_token


client = TestClient(app)


def create_test_data():
    db = SessionLocal()

    user = User(
        user_id=uuid.uuid4(),
        username=f"feedback_test_{uuid.uuid4().hex[:8]}",
        email=f"feedback_{uuid.uuid4().hex[:8]}@example.com",
        role="engineer",
    )

    incident = Incident(
        incident_id=uuid.uuid4(),
        user_id=user.user_id,
        title="Feedback Test Incident",
        description="Database connection failure during payment processing.",
        severity="high",
        status="open",
        source="payment-service",
    )

    output = AgentOutput(
        output_id=uuid.uuid4(),
        incident_id=incident.incident_id,
        agent_name="reasoning_agent",
        agent_type="reasoning",
        diagnosis="Database connection pool exhausted",
        recommendation="Increase database connection pool capacity.",
        reasoning="Strong evidence from logs and metrics.",
    )

    db.add(user)
    db.add(incident)
    db.add(output)
    db.commit()

    ids = {
        "user_id": str(user.user_id),
        "incident_id": str(incident.incident_id),
        "output_id": str(output.output_id),
    }

    db.close()
    return ids


def engineer_headers(user_id):
    token = create_access_token(
        user_id=uuid.UUID(user_id),
        username="feedback_test_user",
        role="engineer",
    )

    return {
        "Authorization": f"Bearer {token}"
    }


def cleanup_test_data(ids):
    db = SessionLocal()

    from app.db.models import Feedback

    # Delete feedback first because it references
    # both the user and agent output.
    feedback_rows = (
        db.query(Feedback)
        .filter(
            Feedback.output_id == uuid.UUID(ids["output_id"]),
            Feedback.user_id == uuid.UUID(ids["user_id"]),
        )
        .all()
    )

    for feedback in feedback_rows:
        db.delete(feedback)

    # Delete agent output next.
    output = db.get(
        AgentOutput,
        uuid.UUID(ids["output_id"]),
    )

    if output:
        db.delete(output)

    # Delete incident next.
    incident = db.get(
        Incident,
        uuid.UUID(ids["incident_id"]),
    )

    if incident:
        db.delete(incident)

    # Delete user last.
    user = db.get(
        User,
        uuid.UUID(ids["user_id"]),
    )

    if user:
        db.delete(user)

    db.commit()
    db.close()


def test_feedback_correct_updates_knowledge_base():
    ids = create_test_data()

    try:
        with patch(
            "app.routers.feedback.add_resolved_incident"
        ) as mock_update:

            mock_update.return_value = {
                "incident_id": ids["incident_id"],
                "chroma_updated": True,
                "neo4j_updated": True,
                "document": "test document",
            }

            response = client.post(
                "/api/feedback/",
                json={
                    "user_id": ids["user_id"],
                    "output_id": ids["output_id"],
                    "rating": 5,
                    "comments": "Diagnosis was correct.",
                    "is_correct": True,
                },
                headers=engineer_headers(ids["user_id"]),
            )

            assert response.status_code == 201

            body = response.json()

            assert body["status"] == "success"
            assert body["message"] == "Feedback submitted successfully"
            assert body["output_id"] == ids["output_id"]
            assert body["knowledge_base_updated"] is True

            mock_update.assert_called_once()

    finally:
        cleanup_test_data(ids)


def test_feedback_incorrect_does_not_update_knowledge_base():
    ids = create_test_data()

    try:
        with patch(
            "app.routers.feedback.add_resolved_incident"
        ) as mock_update:

            response = client.post(
                "/api/feedback/",
                json={
                    "user_id": ids["user_id"],
                    "output_id": ids["output_id"],
                    "rating": 1,
                    "comments": "Diagnosis was incorrect.",
                    "is_correct": False,
                },
                headers=engineer_headers(ids["user_id"]),
            )

            assert response.status_code == 201

            body = response.json()

            assert body["status"] == "success"
            assert body["knowledge_base_updated"] is False

            mock_update.assert_not_called()

    finally:
        cleanup_test_data(ids)


def test_feedback_invalid_user():
    ids = create_test_data()

    try:
        response = client.post(
            "/api/feedback/",
            json={
                "user_id": str(uuid.uuid4()),
                "output_id": ids["output_id"],
                "rating": 5,
                "is_correct": True,
            },
            headers=engineer_headers(ids["user_id"]),
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "User not found"

    finally:
        cleanup_test_data(ids)


def test_feedback_invalid_output():
    ids = create_test_data()

    try:
        response = client.post(
            "/api/feedback/",
            json={
                "user_id": ids["user_id"],
                "output_id": str(uuid.uuid4()),
                "rating": 5,
                "is_correct": True,
            },
            headers=engineer_headers(ids["user_id"]),
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Agent output not found"

    finally:
        cleanup_test_data(ids)


def test_feedback_invalid_rating():
    ids = create_test_data()

    try:
        response = client.post(
            "/api/feedback/",
            json={
                "user_id": ids["user_id"],
                "output_id": ids["output_id"],
                "rating": 6,
                "is_correct": True,
            },
            headers=engineer_headers(ids["user_id"]),
        )

        assert response.status_code == 422

    finally:
        cleanup_test_data(ids)

def create_analytics_test_data():
    db = SessionLocal()

    user = User(
        user_id=uuid.uuid4(),
        username=f"analytics_test_{uuid.uuid4().hex[:8]}",
        email=f"analytics_{uuid.uuid4().hex[:8]}@example.com",
        role="engineer",
    )

    db.add(user)
    db.flush()

    incident_ids = []
    output_ids = []

    # Create 3 feedback records:
    # 2 correct + 1 incorrect
    for is_correct in [True, True, False]:
        incident = Incident(
            incident_id=uuid.uuid4(),
            user_id=user.user_id,
            title="Analytics Feedback Incident",
            description="Analytics test incident.",
            severity="medium",
            status="open",
            source="analytics-test",
            created_at=datetime(2026, 9, 22, 10, 0, 0),
            updated_at=datetime(2026, 9, 22, 10, 30, 0),
        )

        output = AgentOutput(
            output_id=uuid.uuid4(),
            incident_id=incident.incident_id,
            agent_name="reasoning_agent",
            agent_type="reasoning",
            diagnosis="Test diagnosis",
            recommendation="Test recommendation",
            reasoning="Test reasoning",
            created_at=datetime(2026, 9, 22, 10, 5, 0),
        )

        feedback = Feedback(
            feedback_id=uuid.uuid4(),
            user_id=user.user_id,
            output_id=output.output_id,
            rating=5 if is_correct else 1,
            comments="Analytics test feedback",
            is_correct=is_correct,
            created_at=datetime(2026, 9, 22, 11, 0, 0),
        )

        db.add(incident)
        db.add(output)
        db.add(feedback)

        incident_ids.append(incident.incident_id)
        output_ids.append(output.output_id)

    # Create one resolved incident for MTTR.
    resolved_incident = Incident(
        incident_id=uuid.uuid4(),
        user_id=user.user_id,
        title="Analytics MTTR Incident",
        description="MTTR test incident.",
        severity="high",
        status="resolved",
        source="analytics-test",
        created_at=datetime(2026, 9, 22, 12, 0, 0),
        updated_at=datetime(2026, 9, 22, 13, 30, 0),
    )

    db.add(resolved_incident)
    db.commit()

    ids = {
        "user_id": str(user.user_id),
        "incident_ids": [str(value) for value in incident_ids]
        + [str(resolved_incident.incident_id)],
        "output_ids": [str(value) for value in output_ids],
    }

    db.close()

    return ids

def cleanup_analytics_test_data(ids):
    db = SessionLocal()

    output_ids = [
        uuid.UUID(value)
        for value in ids["output_ids"]
    ]

    incident_ids = [
        uuid.UUID(value)
        for value in ids["incident_ids"]
    ]

    # Delete feedback first.
    feedback_rows = (
        db.query(Feedback)
        .filter(Feedback.output_id.in_(output_ids))
        .all()
    )

    for feedback in feedback_rows:
        db.delete(feedback)

    # Delete agent outputs.
    outputs = (
        db.query(AgentOutput)
        .filter(AgentOutput.output_id.in_(output_ids))
        .all()
    )

    for output in outputs:
        db.delete(output)

    # Delete incidents.
    incidents = (
        db.query(Incident)
        .filter(Incident.incident_id.in_(incident_ids))
        .all()
    )

    for incident in incidents:
        db.delete(incident)

    # Delete test user.
    user = db.get(
        User,
        uuid.UUID(ids["user_id"]),
    )

    if user:
        db.delete(user)

    db.commit()
    db.close()

def test_feedback_accuracy_daily_analytics():
    ids = create_analytics_test_data()

    try:
        from app.feedback_analytics import clear_analytics_cache

        clear_analytics_cache()

        response = client.get(
            "/api/feedback/analytics/accuracy?period=daily",
            headers=engineer_headers(ids["user_id"]),
        )

        assert response.status_code == 200

        body = response.json()

        assert body["period"] == "daily"

        row = next(
            item
            for item in body["data"]
            if item["period"] == "2026-09-22"
        )

        assert row["total_feedback"] >= 3
        assert row["correct_feedback"] >= 2
        assert row["incorrect_feedback"] >= 1
        assert row["accuracy"] > 0

    finally:
        cleanup_analytics_test_data(ids)


def test_feedback_accuracy_weekly_analytics():
    ids = create_analytics_test_data()

    try:
        from app.feedback_analytics import clear_analytics_cache

        clear_analytics_cache()

        response = client.get(
            "/api/feedback/analytics/accuracy?period=weekly",
            headers=engineer_headers(ids["user_id"]),
        )

        assert response.status_code == 200

        body = response.json()

        assert body["period"] == "weekly"

        row = next(
            item
            for item in body["data"]
            if item["period"] == "2026-W39"
        )

        assert row["total_feedback"] >= 3
        assert row["correct_feedback"] >= 2
        assert row["incorrect_feedback"] >= 1

    finally:
        cleanup_analytics_test_data(ids)

def test_feedback_mttr_daily_analytics():
    ids = create_analytics_test_data()

    try:
        from app.feedback_analytics import clear_analytics_cache

        clear_analytics_cache()

        response = client.get(
            "/api/feedback/analytics/mttr?period=daily",
            headers=engineer_headers(ids["user_id"]),
        )

        assert response.status_code == 200

        body = response.json()

        assert body["period"] == "daily"

        row = next(
            item
            for item in body["data"]
            if item["period"] == "2026-09-22"
        )

        assert row["resolved_incidents"] >= 1
        assert row["mttr_seconds"] > 0
        assert row["mttr_minutes"] > 0

    finally:
        cleanup_analytics_test_data(ids)


def test_feedback_mttr_weekly_analytics():
    ids = create_analytics_test_data()

    try:
        from app.feedback_analytics import clear_analytics_cache

        clear_analytics_cache()

        response = client.get(
            "/api/feedback/analytics/mttr?period=weekly",
            headers=engineer_headers(ids["user_id"]),
        )

        assert response.status_code == 200

        body = response.json()

        assert body["period"] == "weekly"

        row = next(
            item
            for item in body["data"]
            if item["period"] == "2026-W39"
        )

        assert row["resolved_incidents"] >= 1
        assert row["mttr_seconds"] > 0
        assert row["mttr_minutes"] > 0

    finally:
        cleanup_analytics_test_data(ids)

def test_feedback_analytics_invalid_period():
    ids = create_analytics_test_data()

    try:
        response = client.get(
            "/api/feedback/analytics/accuracy?period=monthly",
            headers=engineer_headers(ids["user_id"]),
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "period must be 'daily' or 'weekly'"
        )

    finally:
        cleanup_analytics_test_data(ids)