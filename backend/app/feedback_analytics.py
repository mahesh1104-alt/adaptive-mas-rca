from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from threading import Lock
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Feedback, Incident


# ============================================================
# SIMPLE IN-MEMORY ANALYTICS CACHE
# ============================================================

_CACHE: dict[str, dict[str, Any]] = {}
_CACHE_LOCK = Lock()

CACHE_TTL_SECONDS = 300


def _get_cached(key: str) -> Any | None:
    with _CACHE_LOCK:
        entry = _CACHE.get(key)

        if entry is None:
            return None

        expires_at = entry["expires_at"]

        if datetime.utcnow() >= expires_at:
            del _CACHE[key]
            return None

        return entry["value"]


def _set_cached(
    key: str,
    value: Any,
    ttl_seconds: int = CACHE_TTL_SECONDS,
) -> None:
    with _CACHE_LOCK:
        _CACHE[key] = {
            "value": value,
            "expires_at": datetime.utcnow()
            + timedelta(seconds=ttl_seconds),
        }


def clear_analytics_cache() -> None:
    """
    Clear cached feedback analytics.

    Called after new feedback is submitted so the next
    dashboard request receives fresh data.
    """

    with _CACHE_LOCK:
        _CACHE.clear()


# ============================================================
# FEEDBACK ACCURACY
# ============================================================

def get_feedback_accuracy(
    db: Session,
    period: str = "daily",
) -> dict[str, Any]:
    """
    Calculate feedback accuracy grouped by day or week.

    Accuracy is:

        correct feedback / feedback with known correctness

    Feedback records where is_correct is NULL are excluded
    from the accuracy denominator.
    """

    if period not in {"daily", "weekly"}:
        raise ValueError(
            "period must be 'daily' or 'weekly'"
        )

    cache_key = f"feedback_accuracy:{period}"

    cached = _get_cached(cache_key)

    if cached is not None:
        return cached

    rows = (
        db.query(
            Feedback.created_at,
            Feedback.is_correct,
        )
        .filter(
            Feedback.is_correct.isnot(None)
        )
        .order_by(
            Feedback.created_at.asc()
        )
        .all()
    )

    buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "total": 0,
            "correct": 0,
            "incorrect": 0,
        }
    )

    for created_at, is_correct in rows:
        if period == "daily":
            bucket = created_at.date().isoformat()
        else:
            # Monday-based ISO week.
            iso_year, iso_week, _ = (
                created_at.isocalendar()
            )
            bucket = (
                f"{iso_year}-W{iso_week:02d}"
            )

        buckets[bucket]["total"] += 1

        if is_correct:
            buckets[bucket]["correct"] += 1
        else:
            buckets[bucket]["incorrect"] += 1

    data = []

    for bucket, values in sorted(
        buckets.items()
    ):
        total = values["total"]

        accuracy = (
            values["correct"] / total
            if total
            else 0.0
        )

        data.append(
            {
                "period": bucket,
                "total_feedback": total,
                "correct_feedback": values[
                    "correct"
                ],
                "incorrect_feedback": values[
                    "incorrect"
                ],
                "accuracy": round(
                    accuracy,
                    4,
                ),
            }
        )

    result = {
        "period": period,
        "data": data,
    }

    _set_cached(
        cache_key,
        result,
    )

    return result


# ============================================================
# MTTR TREND
# ============================================================

def get_mttr_trend(
    db: Session,
    period: str = "daily",
) -> dict[str, Any]:
    """
    Calculate Mean Time To Resolution grouped by day or week.

    MTTR is calculated as:

        incident.updated_at - incident.created_at

    Only resolved incidents with both timestamps are included.
    """

    if period not in {"daily", "weekly"}:
        raise ValueError(
            "period must be 'daily' or 'weekly'"
        )

    cache_key = f"mttr_trend:{period}"

    cached = _get_cached(cache_key)

    if cached is not None:
        return cached

    rows = (
        db.query(
            Incident.created_at,
            Incident.updated_at,
        )
        .filter(
            Incident.status == "resolved",
            Incident.created_at.isnot(None),
            Incident.updated_at.isnot(None),
        )
        .order_by(
            Incident.created_at.asc()
        )
        .all()
    )

    buckets: dict[str, list[float]] = defaultdict(
        list
    )

    for created_at, updated_at in rows:
        duration = (
            updated_at - created_at
        ).total_seconds()

        # Ignore invalid negative durations.
        if duration < 0:
            continue

        if period == "daily":
            bucket = created_at.date().isoformat()
        else:
            iso_year, iso_week, _ = (
                created_at.isocalendar()
            )
            bucket = (
                f"{iso_year}-W{iso_week:02d}"
            )

        buckets[bucket].append(
            duration
        )

    data = []

    for bucket, durations in sorted(
        buckets.items()
    ):
        average_seconds = (
            sum(durations) / len(durations)
        )

        data.append(
            {
                "period": bucket,
                "resolved_incidents": len(
                    durations
                ),
                "mttr_seconds": round(
                    average_seconds,
                    2,
                ),
                "mttr_minutes": round(
                    average_seconds / 60,
                    2,
                ),
            }
        )

    result = {
        "period": period,
        "data": data,
    }

    _set_cached(
        cache_key,
        result,
    )

    return result