import uuid

from fastapi.testclient import TestClient

from app.agents.knowledge_retrieval_agent import KnowledgeRetrievalAgent
from app.db.models import AgentOutput, Incident, Feedback
from app.dependencies import SessionLocal
from app.main import app
from app.security import create_access_token
from app.vector_store import collection


client = TestClient(app)

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


def test_continuous_learning_feedback_to_retrieval():
    """
    Verify the continuous-learning loop:

    engineer-confirmed feedback
        -> knowledge-base update
        -> ChromaDB storage
        -> similar-incident retrieval
    """

    db = SessionLocal()

    incident_id = uuid.uuid4()
    output_id = uuid.uuid4()

    incident = Incident(
        incident_id=incident_id,
        user_id=uuid.UUID(ENGINEER_USER_ID),
        title="Task 78 Payment Timeout",
        description=(
            "Payment service experiences repeated upstream "
            "gateway timeout errors during checkout."
        ),
        severity="high",
        status="open",
        source="payment-service",
    )

    output = AgentOutput(
        output_id=output_id,
        incident_id=incident_id,
        agent_name="reasoning_agent",
        agent_type="reasoning",
        diagnosis="Upstream payment gateway timeout",
        recommendation=(
            "Increase payment gateway timeout handling "
            "and retry transient upstream failures."
        ),
        reasoning=(
            "Repeated timeout errors from payment-service "
            "indicate an upstream gateway timeout."
        ),
    )

    db.add(incident)
    db.add(output)
    db.commit()

    try:
        # --------------------------------------------------
        # 1. Submit engineer-confirmed feedback
        # --------------------------------------------------

        response = client.post(
            "/api/feedback/",
            json={
                "user_id": ENGINEER_USER_ID,
                "output_id": str(output_id),
                "rating": 5,
                "comments": (
                    "Verified root cause for Task 78 "
                    "continuous-learning test."
                ),
                "is_correct": True,
            },
            headers=engineer_headers(),
        )

        assert response.status_code == 201

        body = response.json()

        assert body["status"] == "success"
        assert body["knowledge_base_updated"] is True

        # --------------------------------------------------
        # 2. Verify incident was marked resolved
        # --------------------------------------------------

        db.expire_all()

        updated_incident = db.get(
            Incident,
            incident_id,
        )

        assert updated_incident is not None
        assert updated_incident.status == "resolved"

        # --------------------------------------------------
        # 3. Verify learned incident exists in ChromaDB
        # --------------------------------------------------

        chroma_result = collection.get(
            ids=[str(incident_id)],
            include=["metadatas", "documents"],
        )

        assert str(incident_id) in chroma_result["ids"]

        index = chroma_result["ids"].index(
            str(incident_id)
        )

        metadata = chroma_result["metadatas"][index]
        document = chroma_result["documents"][index]

        assert metadata["service"] == "payment-service"
        assert metadata["knowledge_source"] == "engineer_verified"
        assert metadata["root_cause"] == (
            "Upstream payment gateway timeout"
        )
        assert (
            "Payment service experiences repeated upstream"
            in document
        )

        # --------------------------------------------------
        # 4. Run actual Knowledge Retrieval Agent
        # --------------------------------------------------

        agent = KnowledgeRetrievalAgent(top_k=5)

        result = agent.run(
            {
                "raw_inputs": {
                    "logs": [
                        {
                            "service": "payment-service",
                            "message": (
                                "upstream gateway timeout "
                                "during checkout"
                            ),
                        }
                    ]
                }
            }
        )

        assert result.status == "completed"
        assert result.metadata["result_count"] > 0

        retrieved_ids = {
            str(item.source_id)
            for item in result.evidence
        }

        assert str(incident_id) in retrieved_ids

        # --------------------------------------------------
        # 5. Verify the learned evidence is engineer verified
        # --------------------------------------------------

        learned_evidence = next(
            item
            for item in result.evidence
            if str(item.source_id) == str(incident_id)
        )

        retrieved_value = learned_evidence.value

        assert (
            retrieved_value["service"]
            == "payment-service"
        )

        assert learned_evidence.relevance > 0

    finally:
        # --------------------------------------------------
        # 6. Clean up ChromaDB
        # --------------------------------------------------

        if collection.get(
            ids=[str(incident_id)],
            include=[],
        )["ids"]:
            collection.delete(
                ids=[str(incident_id)]
            )

        # --------------------------------------------------
        # 7. Clean up database records
        # --------------------------------------------------

        db.rollback()

        feedback_rows = db.execute(
            Feedback.__table__.delete().where(
                Feedback.output_id == output_id
            )
        )

        db.execute(
            AgentOutput.__table__.delete().where(
                AgentOutput.output_id == output_id
            )
        )

        db.execute(
            Incident.__table__.delete().where(
                Incident.incident_id == incident_id
            )
        )

        db.commit()
        db.close()
