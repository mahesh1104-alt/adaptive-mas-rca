import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import (
    AgentOutput,
    ConfidenceScore,
    Incident,
    User,
)
from app.dependencies import (
    get_db_session,
    require_engineer,
)
from app.graph import graph
from app.models.diagnosis import (
    DiagnosisRequest,
    DiagnosisResponse,
)


router = APIRouter(
    prefix="/api/diagnosis",
    tags=["Diagnosis"],
)


def _json_text(value: Any) -> str | None:
    """
    Convert structured agent output into text suitable for
    the normalized agent_outputs table.
    """

    if value is None:
        return None

    if isinstance(value, str):
        return value

    return json.dumps(
        value,
        default=str,
        ensure_ascii=False,
    )


def _build_raw_inputs(
    incident: Incident,
    supplied_inputs: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Build the LangGraph raw_inputs payload.

    If the caller supplied raw observability data, preserve it.
    Otherwise construct a minimal payload from the stored incident.
    """

    if supplied_inputs is not None:
        raw_inputs = dict(supplied_inputs)

    else:
        raw_inputs = {}

    raw_inputs.setdefault("logs", [])
    raw_inputs.setdefault("metric_anomalies", [])
    raw_inputs.setdefault("trace", [])
    raw_inputs.setdefault("source_snippets", [])
    raw_inputs.setdefault("recent_commits", [])

    raw_inputs.setdefault(
        "incident_start",
        incident.created_at.isoformat()
        if incident.created_at
        else "",
    )

    raw_inputs.setdefault(
        "incident_end",
        incident.updated_at.isoformat()
        if incident.updated_at
        else "",
    )

    # Give the log agent at least the incident information when
    # no raw logs were supplied.
    if not raw_inputs["logs"]:
        raw_inputs["logs"] = [
            {
                "service": incident.source,
                "message": incident.description,
                "timestamp": (
                    incident.created_at.isoformat()
                    if incident.created_at
                    else None
                ),
            }
        ]

    return raw_inputs


def _persist_graph_result(
    db: Session,
    incident: Incident,
    agent_outputs: dict[str, Any],
) -> dict[str, Any]:
    """
    Persist every graph agent output and its confidence score.
    """

    persisted_outputs = {}

    for agent_name, output in agent_outputs.items():

        if not isinstance(output, dict):
            continue

        metadata = output.get("metadata") or {}

        agent_output = AgentOutput(
            incident_id=incident.incident_id,
            agent_name=agent_name,
            agent_type=agent_name,
            diagnosis=output.get("summary"),
            recommendation=_json_text(
                metadata.get("recommended_actions")
            ),
            reasoning=_json_text(output),
            created_at=datetime.utcnow(),
        )

        db.add(agent_output)
        db.flush()

        confidence = output.get("confidence")

        if confidence is not None:
            try:
                confidence_value = float(confidence)
            except (TypeError, ValueError):
                confidence_value = 0.0

            confidence_value = max(
                0.0,
                min(1.0, confidence_value),
            )

            confidence_score = ConfidenceScore(
                output_id=agent_output.output_id,
                score=confidence_value,
                confidence_level=(
                    "high"
                    if confidence_value >= 0.8
                    else "medium"
                    if confidence_value >= 0.5
                    else "low"
                ),
                explanation=output.get("summary"),
                created_at=datetime.utcnow(),
            )

            db.add(confidence_score)

        persisted_outputs[agent_name] = output

    return persisted_outputs


@router.post(
    "",
    response_model=DiagnosisResponse,
    status_code=status.HTTP_200_OK,
)
def diagnose(
    request: DiagnosisRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(require_engineer),
):
    """
    Run the complete multi-agent RCA pipeline.

    The caller can either:
    1. provide an existing incident_id, or
    2. provide raw_inputs and user_id to create an incident.
    """

    # ============================================================
    # CASE 1: Existing incident
    # ============================================================

    if request.incident_id is not None:

        incident = db.get(
            Incident,
            request.incident_id,
        )

        if incident is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found",
            )

        raw_inputs = _build_raw_inputs(
            incident,
            request.raw_inputs,
        )

    # ============================================================
    # CASE 2: Raw payload
    # ============================================================

    else:

        if request.user_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Either incident_id or user_id with raw_inputs "
                    "must be provided."
                ),
            )

        user = db.get(
            User,
            request.user_id,
        )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        raw_inputs = dict(
            request.raw_inputs or {}
        )

        description = (
            request.description
            or raw_inputs.get("description")
            or "Incident created from diagnosis request."
        )

        title = (
            request.title
            or raw_inputs.get("title")
            or "RCA Diagnosis Incident"
        )

        severity = (
            request.severity
            or raw_inputs.get("severity")
            or "medium"
        )

        incident_status = (
            request.status
            or raw_inputs.get("status")
            or "open"
        )

        source = (
            request.source
            or raw_inputs.get("source")
        )

        incident = Incident(
            user_id=request.user_id,
            title=title,
            description=description,
            severity=severity,
            status=incident_status,
            source=source,
            created_at=datetime.utcnow(),
        )

        db.add(incident)
        db.flush()

        raw_inputs.setdefault("logs", [])
        raw_inputs.setdefault("metric_anomalies", [])
        raw_inputs.setdefault("trace", [])
        raw_inputs.setdefault("source_snippets", [])
        raw_inputs.setdefault("recent_commits", [])
        raw_inputs.setdefault("incident_start", "")
        raw_inputs.setdefault("incident_end", "")

    # ============================================================
    # Invoke compiled LangGraph
    # ============================================================

    graph_inputs = {
        "raw_inputs": raw_inputs,
        "agent_outputs": {},
    }

    try:

        graph_result = graph.invoke(
            graph_inputs
        )

    except Exception as exc:

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Diagnosis pipeline failed: {str(exc)}",
        )

    agent_outputs = graph_result.get(
        "agent_outputs",
        {},
    )

    if not isinstance(agent_outputs, dict):
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Diagnosis pipeline returned an invalid result.",
        )

    # ============================================================
    # Extract final report
    # ============================================================

    reasoning_output = agent_outputs.get(
        "reasoning_agent",
        {},
    )

    final_report = {}

    if isinstance(reasoning_output, dict):

        metadata = reasoning_output.get(
            "metadata",
            {},
        )

        if isinstance(metadata, dict):

            final_report = metadata.get(
                "final_report",
                {},
            )

    if not isinstance(final_report, dict):
        final_report = {}

    # ============================================================
    # Persist agent outputs + confidence scores
    # ============================================================

    try:

        persisted_outputs = _persist_graph_result(
            db=db,
            incident=incident,
            agent_outputs=agent_outputs,
        )

        incident.updated_at = datetime.utcnow()

        db.commit()

    except Exception as exc:

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to persist diagnosis: {str(exc)}",
        )

    return {
        "status": "success",
        "incident_id": incident.incident_id,
        "report": final_report,
        "agent_outputs": persisted_outputs,
    }