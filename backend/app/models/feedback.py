import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    user_id: uuid.UUID
    output_id: uuid.UUID
    rating: int | None = Field(default=None, ge=1, le=5)
    comments: str | None = None
    is_correct: bool | None = None


class FeedbackResponse(BaseModel):
    status: str
    message: str
    feedback_id: uuid.UUID
    output_id: uuid.UUID
    knowledge_base_updated: bool


__all__ = [
    "FeedbackCreate",
    "FeedbackResponse",
]
