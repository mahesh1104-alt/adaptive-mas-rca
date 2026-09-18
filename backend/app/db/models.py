import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    username: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )

    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=datetime.utcnow,
    )

    incidents: Mapped[list["Incident"]] = relationship(
        back_populates="user"
    )

    feedback: Mapped[list["Feedback"]] = relationship(
        back_populates="user"
    )


class Incident(Base):
    __tablename__ = "incidents"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    source: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )

    user: Mapped["User"] = relationship(
        back_populates="incidents"
    )

    agent_outputs: Mapped[list["AgentOutput"]] = relationship(
        back_populates="incident"
    )


class AgentOutput(Base):
    __tablename__ = "agent_outputs"

    output_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.incident_id"),
        nullable=False,
    )

    agent_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    agent_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    diagnosis: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    recommendation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    reasoning: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=datetime.utcnow,
    )

    incident: Mapped["Incident"] = relationship(
        back_populates="agent_outputs"
    )

    confidence_scores: Mapped[list["ConfidenceScore"]] = relationship(
        back_populates="output"
    )

    feedback: Mapped[list["Feedback"]] = relationship(
        back_populates="output"
    )


class ConfidenceScore(Base):
    __tablename__ = "confidence_scores"

    confidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    output_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_outputs.output_id"),
        nullable=False,
    )

    score: Mapped[float] = mapped_column(
        Numeric(5, 4),
        nullable=False,
    )

    confidence_level: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    explanation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=datetime.utcnow,
    )

    output: Mapped["AgentOutput"] = relationship(
        back_populates="confidence_scores"
    )


class Feedback(Base):
    __tablename__ = "feedback"

    feedback_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False,
    )

    output_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_outputs.output_id"),
        nullable=False,
    )

    rating: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    comments: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_correct: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=datetime.utcnow,
    )

    user: Mapped["User"] = relationship(
        back_populates="feedback"
    )

    output: Mapped["AgentOutput"] = relationship(
        back_populates="feedback"
    )