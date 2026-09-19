from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Any


_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def create_job(
    incident_id: uuid.UUID,
    user_id: uuid.UUID,
) -> str:
    job_id = str(uuid.uuid4())

    job = {
        "job_id": job_id,
        "incident_id": str(incident_id),
        "user_id": str(user_id),
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "started_at": None,
        "completed_at": None,
        "report": {},
        "agent_outputs": {},
        "error": None,
    }

    with _jobs_lock:
        _jobs[job_id] = job

    return job_id


def get_job(job_id: str) -> dict[str, Any] | None:
    with _jobs_lock:
        job = _jobs.get(job_id)

        if job is None:
            return None

        return dict(job)


def update_job(
    job_id: str,
    **updates: Any,
) -> None:
    with _jobs_lock:
        if job_id not in _jobs:
            return

        _jobs[job_id].update(updates)


def mark_running(job_id: str) -> None:
    update_job(
        job_id,
        status="running",
        started_at=datetime.utcnow().isoformat(),
    )


def mark_completed(
    job_id: str,
    report: dict[str, Any],
    agent_outputs: dict[str, Any],
) -> None:
    update_job(
        job_id,
        status="completed",
        completed_at=datetime.utcnow().isoformat(),
        report=report,
        agent_outputs=agent_outputs,
        error=None,
    )


def mark_failed(
    job_id: str,
    error: str,
) -> None:
    update_job(
        job_id,
        status="failed",
        completed_at=datetime.utcnow().isoformat(),
        error=error,
    )