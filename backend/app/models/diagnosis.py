from typing import Any
import uuid

from pydantic import BaseModel, Field


class DiagnosisRequest(BaseModel):
    incident_id: uuid.UUID | None = None

    # Used when no incident_id is supplied.
    # The graph receives this dictionary as raw_inputs.
    raw_inputs: dict[str, Any] | None = None

    # Required when creating an incident from a raw payload.
    user_id: uuid.UUID | None = None

    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    severity: str | None = Field(default="medium", max_length=20)
    status: str | None = Field(default="open", max_length=30)
    source: str | None = Field(default=None, max_length=100)


class DiagnosisResponse(BaseModel):
    status: str
    incident_id: uuid.UUID
    report: dict[str, Any]
    agent_outputs: dict[str, Any]