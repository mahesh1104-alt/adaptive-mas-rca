import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests


# ============================================================
# CONFIGURATION
# ============================================================

LOG_DIR = os.getenv("LOG_DIR", "/logs")

PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL",
    "http://prometheus:9090",
)

JAEGER_URL = os.getenv(
    "JAEGER_URL",
    "http://jaeger:16686",
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _parse_timestamp(timestamp: Optional[str]) -> Optional[datetime]:
    """
    Convert an ISO-8601 timestamp into a datetime object.
    Returns None when no timestamp is supplied.
    """
    if not timestamp:
        return None

    value = timestamp.strip()

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _timestamp_in_range(
    timestamp: Optional[str],
    start_time: Optional[str],
    end_time: Optional[str],
) -> bool:
    """
    Check whether a record timestamp falls inside the
    requested time window.
    """

    record_time = _parse_timestamp(timestamp)

    if record_time is None:
        return False

    start = _parse_timestamp(start_time)
    end = _parse_timestamp(end_time)

    if start is not None and record_time < start:
        return False

    if end is not None and record_time > end:
        return False

    return True


# ============================================================
# LOG STORAGE
# ============================================================

def query_logs(
    service: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Query raw logs stored as JSONL files.

    Each service has its own file:

        /logs/<service>.jsonl
    """

    log_file = os.path.join(
        LOG_DIR,
        f"{service}.jsonl",
    )

    if not os.path.exists(log_file):
        return []

    results: List[Dict[str, Any]] = []

    with open(
        log_file,
        "r",
        encoding="utf-8",
    ) as file:

        for line in file:
            line = line.strip()

            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            timestamp = record.get("timestamp")

            if not _timestamp_in_range(
                timestamp,
                start_time,
                end_time,
            ):
                continue

            results.append(record)

    return results


# ============================================================
# METRIC STORAGE
# ============================================================

def query_metrics(
    service: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    metric_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Query metrics from Prometheus using its HTTP API.

    A PromQL selector is constructed for the service and,
    when provided, a metric name.
    """

    if metric_name:
        query = (
            f'{metric_name}{{job="{service}"}}'
        )
    else:
        query = (
            f'{{job="{service}"}}'
        )

    params: Dict[str, str] = {
        "query": query,
    }

    if start_time and end_time:
        params["start"] = start_time
        params["end"] = end_time

    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        return response.json()

    except requests.RequestException as exc:
        return {
            "status": "error",
            "error": str(exc),
            "data": {
                "resultType": "vector",
                "result": [],
            },
        }


# ============================================================
# TRACE STORAGE
# ============================================================

def query_traces(
    service: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    Query traces from the Jaeger query API.

    Jaeger expects timestamps in microseconds for
    start and end parameters.
    """

    params: Dict[str, Any] = {
        "service": service,
        "limit": limit,
    }

    start = _parse_timestamp(start_time)
    end = _parse_timestamp(end_time)

    if start is not None:
        params["start"] = int(
            start.timestamp() * 1_000_000
        )

    if end is not None:
        params["end"] = int(
            end.timestamp() * 1_000_000
        )

    try:
        response = requests.get(
            f"{JAEGER_URL}/api/traces",
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        return response.json()

    except requests.RequestException as exc:
        return {
            "data": [],
            "total": 0,
            "limit": limit,
            "errors": [
                {
                    "code": "query_error",
                    "msg": str(exc),
                }
            ],
        }