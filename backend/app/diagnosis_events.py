from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from queue import Queue
from typing import Any


_MAX_HISTORY = 100

_subscribers: dict[str, set[Queue]] = {}
_history: dict[str, list[dict[str, Any]]] = {}

_lock = threading.Lock()


def publish_event(
    job_id: str,
    event: str,
    **data: Any,
) -> dict[str, Any]:
    """
    Publish a diagnosis progress event.

    Events are stored briefly so a WebSocket client that connects
    after an event was emitted can still receive recent progress.
    """

    message = {
        "event": event,
        "job_id": str(job_id),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **data,
    }

    with _lock:
        history = _history.setdefault(str(job_id), [])
        history.append(message)

        if len(history) > _MAX_HISTORY:
            del history[:-_MAX_HISTORY]

        subscribers = list(
            _subscribers.get(str(job_id), set())
        )

    for subscriber in subscribers:
        subscriber.put(message)

    return message


def subscribe(
    job_id: str,
) -> tuple[Queue, list[dict[str, Any]]]:
    """
    Subscribe to a diagnosis job.

    Returns:
        queue: receives future events
        history: events emitted before subscription
    """

    job_id = str(job_id)
    queue: Queue = Queue()

    with _lock:
        subscribers = _subscribers.setdefault(
            job_id,
            set(),
        )

        subscribers.add(queue)

        history = list(
            _history.get(job_id, [])
        )

    return queue, history


def unsubscribe(
    job_id: str,
    queue: Queue,
) -> None:
    job_id = str(job_id)

    with _lock:
        subscribers = _subscribers.get(job_id)

        if not subscribers:
            return

        subscribers.discard(queue)

        if not subscribers:
            _subscribers.pop(job_id, None)


def clear_job_events(
    job_id: str,
) -> None:
    """
    Remove stored event history after a job has finished.
    """

    job_id = str(job_id)

    with _lock:
        _history.pop(job_id, None)