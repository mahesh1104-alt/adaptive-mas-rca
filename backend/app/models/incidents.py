import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class IncidentCreate(BaseModel):
    user_id: uuid.UUID
    title: str = Field(..., max_length=255)
    description: str
    severity: str = Field(..., max_length=20)
    status: str = Field(..., max_length=30)
    source: str | None = Field(default=None, max_length=100)


class IncidentResponse(BaseModel):
    incident_id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: str
    severity: str
    status: str
    source: str | None
    created_at: datetime
    updated_at: datetime | None

    model_config = {
        "from_attributes": True
    }


class IncidentStatusUpdate(BaseModel):
    status: str = Field(..., max_length=30)