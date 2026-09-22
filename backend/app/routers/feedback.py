import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import (
    get_db_session,
    require_engineer,
)
from app.db.models import User, AgentOutput, Incident, Feedback
from app.models.feedback import FeedbackCreate, FeedbackResponse
from app.knowledge_base_updater import add_resolved_incident


router = APIRouter(
    prefix="/api/feedback",
    tags=["Feedback"],
)


@router.get("/")
def feedback_status():
    return {
        "status": "success",
        "message": "Feedback router is working",
    }


@router.post(
    "/",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_feedback(
    payload: FeedbackCreate,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(require_engineer),
):
    # --------------------------------------------------------
    # Validate user
    # --------------------------------------------------------

    user = db.get(User, payload.user_id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    # --------------------------------------------------------
    # Validate agent output
    # --------------------------------------------------------

    output = db.get(
        AgentOutput,
        payload.output_id,
    )

    if output is None:
        raise HTTPException(
            status_code=404,
            detail="Agent output not found",
        )

    # --------------------------------------------------------
    # Get associated incident
    # --------------------------------------------------------

    incident = db.get(
        Incident,
        output.incident_id,
    )

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail="Incident associated with agent output not found",
        )

    # --------------------------------------------------------
    # Create feedback record
    # --------------------------------------------------------

    feedback = Feedback(
        feedback_id=uuid.uuid4(),
        user_id=payload.user_id,
        output_id=payload.output_id,
        rating=payload.rating,
        comments=payload.comments,
        is_correct=payload.is_correct,
        created_at=datetime.utcnow(),
    )

    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    # --------------------------------------------------------
    # Knowledge-base update
    #
    # Only learn from explicitly confirmed/correct feedback.
    # The existing Phase-5 updater requires a root cause.
    # --------------------------------------------------------

    knowledge_base_updated = False

    if payload.is_correct is True:
        # Mark the incident as resolved when an engineer
        # confirms that the diagnosis is correct.
        incident.status = "resolved"
        incident.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(incident)

        root_cause = output.diagnosis

        if root_cause:
            kb_incident = {
                "incident_id": str(incident.incident_id),
                "alert_name": incident.title,
                "service": incident.source or "",
                "severity": incident.severity,
                "status": "resolved",
                "started_at": incident.created_at.isoformat(),
                "resolved_at": datetime.utcnow().isoformat(),
                "summary": incident.title,
                "description": incident.description,
                "root_cause": root_cause,
                "resolution": (
                    output.recommendation or ""
                ),
                "knowledge_source": "engineer_verified",
                "resolution_confidence": 1.0,
            }

            try:
                add_resolved_incident(kb_incident)
                knowledge_base_updated = True
            except Exception:
                knowledge_base_updated = False

    return FeedbackResponse(
        status="success",
        message="Feedback submitted successfully",
        feedback_id=feedback.feedback_id,
        output_id=feedback.output_id,
        knowledge_base_updated=knowledge_base_updated,
    )
