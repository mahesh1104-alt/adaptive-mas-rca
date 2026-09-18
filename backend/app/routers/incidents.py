import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Incident, User
from app.dependencies import get_db_session
from app.models.incidents import (
    IncidentCreate,
    IncidentResponse,
    IncidentStatusUpdate,
)


router = APIRouter(
    prefix="/api/incidents",
    tags=["Incidents"],
)


# ============================================================
# POST /api/incidents
# Create a new incident
# ============================================================

@router.post(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_incident(
    incident_data: IncidentCreate,
    db: Session = Depends(get_db_session),
):
    # Verify that the user exists
    user = db.get(User, incident_data.user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    incident = Incident(
        user_id=incident_data.user_id,
        title=incident_data.title,
        description=incident_data.description,
        severity=incident_data.severity,
        status=incident_data.status,
        source=incident_data.source,
        created_at=datetime.utcnow(),
    )

    db.add(incident)
    db.commit()
    db.refresh(incident)

    return incident


# ============================================================
# GET /api/incidents
# List all incidents
# ============================================================

@router.get(
    "",
    response_model=list[IncidentResponse],
)
def list_incidents(
    db: Session = Depends(get_db_session),
):
    statement = (
        select(Incident)
        .order_by(Incident.created_at.desc())
    )

    incidents = db.scalars(statement).all()

    return incidents


# ============================================================
# GET /api/incidents/{incident_id}
# Get incident details
# ============================================================

@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
)
def get_incident(
    incident_id: uuid.UUID,
    db: Session = Depends(get_db_session),
):
    incident = db.get(Incident, incident_id)

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    return incident


# ============================================================
# PUT /api/incidents/{incident_id}
# Update incident status
# ============================================================

@router.put(
    "/{incident_id}",
    response_model=IncidentResponse,
)
def update_incident_status(
    incident_id: uuid.UUID,
    status_data: IncidentStatusUpdate,
    db: Session = Depends(get_db_session),
):
    incident = db.get(Incident, incident_id)

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    incident.status = status_data.status
    incident.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(incident)

    return incident