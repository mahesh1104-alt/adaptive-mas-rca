"""
Trace preprocessing module for Adaptive MAS RCA.

Responsibilities:
- Parse Jaeger trace JSON.
- Convert raw Jaeger spans into a simplified span representation.
- Calculate per-span duration.
- Build parent/child relationships.
- Identify the critical path.
- Detect slow spans using a percentile threshold.
- Detect error spans.
- Produce a simplified trace summary.

The module is intentionally independent from FastAPI so that it can be
tested directly and reused by other components of the RCA pipeline.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import math
import statistics


# ============================================================
# TYPE ALIASES
# ============================================================

Span = Dict[str, Any]
SimplifiedSpan = Dict[str, Any]


# ============================================================
# GENERAL HELPERS
# ============================================================

def _safe_float(value: Any, default: float = 0.0) -> float:
    """
    Convert a value to float safely.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    """
    Convert a value to int safely.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _percentile(values: List[float], percentile: float) -> float:
    """
    Calculate a percentile using linear interpolation.

    Example:
        percentile = 95 means the 95th percentile.

    Empty input returns 0.
    """
    if not values:
        return 0.0

    values = sorted(values)

    if len(values) == 1:
        return values[0]

    percentile = max(0.0, min(100.0, percentile))

    rank = (percentile / 100.0) * (len(values) - 1)

    lower_index = int(math.floor(rank))
    upper_index = int(math.ceil(rank))

    if lower_index == upper_index:
        return values[lower_index]

    lower_value = values[lower_index]
    upper_value = values[upper_index]

    fraction = rank - lower_index

    return lower_value + (
        (upper_value - lower_value) * fraction
    )


def _normalize_status(value: Any) -> str:
    """
    Normalize span status values.
    """
    if value is None:
        return "UNSET"

    value = str(value).strip().upper()

    if value in {"ERROR", "ERR", "FAILED", "FAIL"}:
        return "ERROR"

    if value in {"OK", "SUCCESS", "SUCCEEDED"}:
        return "OK"

    return value or "UNSET"


# ============================================================
# JAEGER TRACE EXTRACTION
# ============================================================

def extract_jaeger_spans(trace_data: Any) -> List[Span]:
    """
    Extract raw spans from common Jaeger JSON structures.

    Supported structures include:

    1. Jaeger query response:

       {
           "data": [
               {
                   "traceID": "...",
                   "spans": [...]
               }
           ]
       }

    2. Single trace:

       {
           "traceID": "...",
           "spans": [...]
       }

    3. Direct span list:

       {
           "spans": [...]
       }

    4. A list of spans.

    Returns:
        List of raw Jaeger span dictionaries.
    """

    if trace_data is None:
        return []

    # Direct list of spans.
    if isinstance(trace_data, list):
        return [
            span
            for span in trace_data
            if isinstance(span, dict)
        ]

    if not isinstance(trace_data, dict):
        return []

    # Standard Jaeger query response.
    data = trace_data.get("data")

    if isinstance(data, list):
        all_spans: List[Span] = []

        for trace in data:
            if not isinstance(trace, dict):
                continue

            spans = trace.get("spans", [])

            if isinstance(spans, list):
                all_spans.extend(
                    span
                    for span in spans
                    if isinstance(span, dict)
                )

        return all_spans

    # A single trace object.
    spans = trace_data.get("spans")

    if isinstance(spans, list):
        return [
            span
            for span in spans
            if isinstance(span, dict)
        ]

    return []


# ============================================================
# TAG / PROCESS HELPERS
# ============================================================

def _tags_to_dict(tags: Any) -> Dict[str, Any]:
    """
    Convert Jaeger tag list into a dictionary.

    Jaeger commonly represents tags as:

        [
            {"key": "http.status_code", "type": "int", "value": 500},
            {"key": "error", "type": "bool", "value": True}
        ]
    """

    result: Dict[str, Any] = {}

    if not isinstance(tags, list):
        return result

    for tag in tags:
        if not isinstance(tag, dict):
            continue

        key = tag.get("key")

        if not key:
            continue

        result[str(key)] = tag.get("value")

    return result


def _extract_service_name(
    span: Dict[str, Any]
) -> str:
    """
    Extract service name from a Jaeger span.

    Jaeger commonly stores it under:
        process.serviceName

    Some test/synthetic traces may store it directly under:
        service
        serviceName
    """

    process = span.get("process")

    if isinstance(process, dict):
        service_name = process.get("serviceName")

        if service_name:
            return str(service_name)

    for key in ("service", "serviceName"):
        value = span.get(key)

        if value:
            return str(value)

    return "unknown-service"


def _extract_operation_name(
    span: Dict[str, Any]
) -> str:
    """
    Extract operation name from a Jaeger span.
    """

    for key in ("operationName", "operation", "name"):
        value = span.get(key)

        if value:
            return str(value)

    return "unknown-operation"


def _extract_parent_id(
    span: Dict[str, Any]
) -> Optional[str]:
    """
    Extract the parent span ID.

    Jaeger may represent references like:

        "references": [
            {
                "refType": "CHILD_OF",
                "traceID": "...",
                "spanID": "..."
            }
        ]

    Some simplified traces may directly use:
        parentSpanID
        parent_id
    """

    for key in ("parentSpanID", "parent_id", "parentId"):
        value = span.get(key)

        if value:
            return str(value)

    references = span.get("references")

    if isinstance(references, list):
        for reference in references:
            if not isinstance(reference, dict):
                continue

            ref_type = str(
                reference.get("refType", "")
            ).upper()

            if ref_type == "CHILD_OF":
                parent_id = reference.get("spanID")

                if parent_id:
                    return str(parent_id)

    return None


def _extract_error(
    span: Dict[str, Any],
    tags: Dict[str, Any]
) -> bool:
    """
    Determine whether a span represents an error.

    Error is detected from:
    - explicit error=true tag
    - span status ERROR
    - error tag
    - HTTP 5xx status
    """

    error_value = tags.get("error")

    if isinstance(error_value, bool):
        if error_value:
            return True

    if str(error_value).lower() == "true":
        return True

    status = _normalize_status(
        span.get("status")
    )

    if status == "ERROR":
        return True

    tags_status = _normalize_status(
        tags.get("status")
    )

    if tags_status == "ERROR":
        return True

    status_code = tags.get(
        "http.status_code"
    )

    if status_code is None:
        status_code = tags.get(
            "http.response.status_code"
        )

    try:
        status_code = int(status_code)

        if status_code >= 500:
            return True

    except (TypeError, ValueError):
        pass

    return False


# ============================================================
# SPAN SIMPLIFICATION
# ============================================================

def simplify_span(
    span: Dict[str, Any],
    trace_id: Optional[str] = None
) -> SimplifiedSpan:
    """
    Convert one raw Jaeger span into a simplified representation.

    Duration is normalized from Jaeger's microseconds to milliseconds.

    Returned structure:

    {
        "span_id": "...",
        "trace_id": "...",
        "parent_span_id": "...",
        "service": "...",
        "operation": "...",
        "start_time_us": 123456,
        "duration_us": 500000,
        "duration_ms": 500.0,
        "status": "OK",
        "error": False,
        "tags": {...}
    }
    """

    if not isinstance(span, dict):
        raise ValueError(
            "Span must be a dictionary"
        )

    span_id = str(
        span.get(
            "spanID",
            span.get(
                "spanId",
                span.get("span_id", "")
            )
        )
    )

    actual_trace_id = trace_id

    if actual_trace_id is None:
        actual_trace_id = span.get(
            "traceID",
            span.get("traceId")
        )

    if actual_trace_id is not None:
        actual_trace_id = str(actual_trace_id)

    start_time_us = _safe_int(
        span.get(
            "startTime",
            span.get(
                "start_time_us",
                0
            )
        )
    )

    duration_us = _safe_int(
        span.get(
            "duration",
            span.get(
                "duration_us",
                0
            )
        )
    )

    tags = _tags_to_dict(
        span.get("tags", [])
    )

    error = _extract_error(
        span,
        tags
    )

    status = (
        "ERROR"
        if error
        else _normalize_status(
            span.get(
                "status",
                tags.get("status")
            )
        )
    )

    return {
        "span_id": span_id,
        "trace_id": actual_trace_id,
        "parent_span_id": _extract_parent_id(
            span
        ),
        "service": _extract_service_name(
            span
        ),
        "operation": _extract_operation_name(
            span
        ),
        "start_time_us": start_time_us,
        "duration_us": duration_us,
        "duration_ms": duration_us / 1000.0,
        "status": status,
        "error": error,
        "tags": tags,
    }


def simplify_trace(
    trace_data: Any
) -> List[SimplifiedSpan]:
    """
    Parse a Jaeger trace and return a simplified span list.
    """

    raw_spans = extract_jaeger_spans(
        trace_data
    )

    return [
        simplify_span(span)
        for span in raw_spans
    ]


# ============================================================
# CRITICAL PATH
# ============================================================

def identify_critical_path(
    spans: List[SimplifiedSpan]
) -> List[SimplifiedSpan]:
    """
    Identify the critical path in a parent/child span tree.

    The critical path is calculated as the chain of spans with the
    greatest cumulative duration.

    For each span:

        path_cost(span) =
            span.duration +
            maximum child path cost

    The algorithm starts at root spans and chooses the root/path with
    the greatest cumulative duration.

    Returns:
        Ordered list of spans from root to the bottleneck/leaf.
    """

    if not spans:
        return []

    span_map: Dict[str, SimplifiedSpan] = {}

    for span in spans:
        span_id = str(
            span.get("span_id", "")
        )

        if span_id:
            span_map[span_id] = span

    if not span_map:
        return []

    children: Dict[str, List[SimplifiedSpan]] = {
        span_id: []
        for span_id in span_map
    }

    roots: List[SimplifiedSpan] = []

    for span in span_map.values():
        parent_id = span.get(
            "parent_span_id"
        )

        if parent_id in span_map:
            children[parent_id].append(span)
        else:
            roots.append(span)

    # If no root can be determined, treat all spans as possible roots.
    if not roots:
        roots = list(span_map.values())

    cache: Dict[str, Tuple[float, List[SimplifiedSpan]]] = {}
    visiting: set[str] = set()

    def best_path(
        span: SimplifiedSpan
    ) -> Tuple[float, List[SimplifiedSpan]]:

        span_id = str(
            span.get("span_id", "")
        )

        if span_id in cache:
            return cache[span_id]

        # Protect against malformed cyclic parent/child data.
        if span_id in visiting:
            return (
                _safe_float(
                    span.get("duration_ms", 0)
                ),
                [span],
            )

        visiting.add(span_id)

        own_duration = _safe_float(
            span.get(
                "duration_ms",
                0
            )
        )

        child_paths = []

        for child in children.get(
            span_id,
            []
        ):
            child_paths.append(
                best_path(child)
            )

        visiting.discard(span_id)

        if not child_paths:
            result = (
                own_duration,
                [span]
            )

            cache[span_id] = result

            return result

        best_child = max(
            child_paths,
            key=lambda item: item[0]
        )

        result = (
            own_duration + best_child[0],
            [span] + best_child[1]
        )

        cache[span_id] = result

        return result

    root_paths = [
        best_path(root)
        for root in roots
    ]

    if not root_paths:
        return []

    return max(
        root_paths,
        key=lambda item: item[0]
    )[1]


# ============================================================
# SLOW SPAN DETECTION
# ============================================================

def detect_slow_spans(
    spans: List[SimplifiedSpan],
    percentile: float = 95.0
) -> List[SimplifiedSpan]:
    """
    Flag spans whose duration is at or above the requested percentile.

    The returned span objects contain:

        slow = True
        slow_threshold_ms = <calculated threshold>

    If the input contains fewer spans, the percentile is still calculated
    safely.
    """

    if not spans:
        return []

    durations = [
        _safe_float(
            span.get(
                "duration_ms",
                0
            )
        )
        for span in spans
    ]

    threshold = _percentile(
        durations,
        percentile
    )

    result: List[SimplifiedSpan] = []

    for span in spans:
        processed = dict(span)

        duration = _safe_float(
            span.get(
                "duration_ms",
                0
            )
        )

        processed["slow_threshold_ms"] = threshold
        processed["slow"] = (
            duration >= threshold
        )

        result.append(processed)

    return result


# ============================================================
# ERROR SPAN DETECTION
# ============================================================

def detect_error_spans(
    spans: List[SimplifiedSpan]
) -> List[SimplifiedSpan]:
    """
    Return only spans that represent errors.
    """

    return [
        span
        for span in spans
        if bool(
            span.get("error", False)
        )
    ]


# ============================================================
# TRACE SUMMARY
# ============================================================

def preprocess_trace(
    trace_data: Any,
    slow_percentile: float = 95.0
) -> Dict[str, Any]:
    """
    Complete trace preprocessing pipeline.

    Steps:
        1. Parse Jaeger spans.
        2. Simplify spans.
        3. Detect slow spans.
        4. Detect error spans.
        5. Identify critical path.
        6. Determine bottleneck.
        7. Determine failing span.

    Returns:

    {
        "trace_id": "...",
        "span_count": 4,
        "spans": [...],
        "critical_path": [...],
        "critical_path_duration_ms": 850.0,
        "slow_threshold_ms": 100.0,
        "slow_spans": [...],
        "error_spans": [...],
        "bottleneck_span": {...},
        "failing_span": {...}
    }
    """

    spans = simplify_trace(
        trace_data
    )

    if not spans:
        return {
            "trace_id": None,
            "span_count": 0,
            "spans": [],
            "critical_path": [],
            "critical_path_duration_ms": 0.0,
            "slow_threshold_ms": 0.0,
            "slow_spans": [],
            "error_spans": [],
            "bottleneck_span": None,
            "failing_span": None,
        }

    processed_spans = detect_slow_spans(
        spans,
        percentile=slow_percentile
    )

    error_spans = detect_error_spans(
        processed_spans
    )

    critical_path = identify_critical_path(
        processed_spans
    )

    critical_path_duration = sum(
        _safe_float(
            span.get(
                "duration_ms",
                0
            )
        )
        for span in critical_path
    )

    slow_spans = [
        span
        for span in processed_spans
        if span.get("slow", False)
    ]

    bottleneck_span = None

    if critical_path:
    # If the trace contains an error span, prefer the deepest
    # error span on the critical path. This is more useful for RCA
    # because upstream spans may inherit the failure from a
    # downstream service.
        critical_path_error_spans = [
            span
            for span in critical_path
            if span.get("error", False)
        ]

        if critical_path_error_spans:
            bottleneck_span = critical_path_error_spans[-1]
        else:
        # For healthy traces, use the longest span on the
        # critical path as the bottleneck.
            bottleneck_span = max(
                critical_path,
                key=lambda span: _safe_float(
                    span.get(
                        "duration_ms",
                        0
                    )
                )
            )


    failing_span = None

    if error_spans:
    # Prefer the deepest error span in the trace.
    # Upstream spans can also be marked as failed because they
    # propagate a downstream failure. The deepest error span is
    # therefore the most useful candidate for RCA.
        critical_path_error_spans = [
            span
            for span in critical_path
            if span.get("error", False)
        ]

        if critical_path_error_spans:
            failing_span = critical_path_error_spans[-1]
        else:
        # Fallback for error spans that are not on the critical path.
            failing_span = error_spans[-1]


    trace_ids = [
        span.get("trace_id")
        for span in processed_spans
        if span.get("trace_id")
    ]

    trace_id = (
        trace_ids[0]
        if trace_ids
        else None
    )

    threshold = (
        processed_spans[0].get(
            "slow_threshold_ms",
            0.0
        )
        if processed_spans
        else 0.0
    )

    return {
        "trace_id": trace_id,
        "span_count": len(processed_spans),
        "spans": processed_spans,
        "critical_path": critical_path,
        "critical_path_duration_ms": critical_path_duration,
        "slow_threshold_ms": threshold,
        "slow_spans": slow_spans,
        "error_spans": error_spans,
        "bottleneck_span": bottleneck_span,
        "failing_span": failing_span,
    }


# ============================================================
# SIMULATED FAULTY REQUEST
# ============================================================

def create_faulty_request_trace() -> Dict[str, Any]:
    """
    Create a deterministic Jaeger-style trace representing a faulty
    request.

    Trace:

        API Gateway
             |
        Order Service
             |
        Inventory Service
             |
        Database

    The Inventory Service is deliberately slow and returns HTTP 500.

    This is useful for deterministic unit/integration testing.
    """

    trace_id = "faulty-trace-001"

    return {
        "data": [
            {
                "traceID": trace_id,
                "spans": [
                    {
                        "traceID": trace_id,
                        "spanID": "span-api",
                        "operationName": "POST /orders",
                        "startTime": 1_000_000,
                        "duration": 500_000,
                        "references": [],
                        "process": {
                            "serviceName": "api-gateway"
                        },
                        "tags": [
                            {
                                "key": "http.status_code",
                                "type": "int",
                                "value": 500
                            }
                        ]
                    },
                    {
                        "traceID": trace_id,
                        "spanID": "span-order",
                        "operationName": "create-order",
                        "startTime": 1_050_000,
                        "duration": 450_000,
                        "references": [
                            {
                                "refType": "CHILD_OF",
                                "traceID": trace_id,
                                "spanID": "span-api"
                            }
                        ],
                        "process": {
                            "serviceName": "order-service"
                        },
                        "tags": []
                    },
                    {
                        "traceID": trace_id,
                        "spanID": "span-inventory",
                        "operationName": "check-inventory",
                        "startTime": 1_100_000,
                        "duration": 350_000,
                        "references": [
                            {
                                "refType": "CHILD_OF",
                                "traceID": trace_id,
                                "spanID": "span-order"
                            }
                        ],
                        "process": {
                            "serviceName": "inventory-service"
                        },
                        "tags": [
                            {
                                "key": "error",
                                "type": "bool",
                                "value": True
                            },
                            {
                                "key": "http.status_code",
                                "type": "int",
                                "value": 500
                            },
                            {
                                "key": "error.message",
                                "type": "string",
                                "value": "Inventory database unavailable"
                            }
                        ]
                    },
                    {
                        "traceID": trace_id,
                        "spanID": "span-db",
                        "operationName": "SELECT inventory",
                        "startTime": 1_150_000,
                        "duration": 300_000,
                        "references": [
                            {
                                "refType": "CHILD_OF",
                                "traceID": trace_id,
                                "spanID": "span-inventory"
                            }
                        ],
                        "process": {
                            "serviceName": "inventory-db"
                        },
                        "tags": [
                            {
                                "key": "db.system",
                                "type": "string",
                                "value": "postgresql"
                            }
                        ]
                    }
                ]
            }
        ]
    }


# ============================================================
# CONVENIENCE SUMMARY FUNCTION
# ============================================================

def summarize_trace(
    trace_data: Any,
    slow_percentile: float = 95.0
) -> Dict[str, Any]:
    """
    Alias for preprocess_trace().

    This provides a simple public function for agents or other modules
    that only need the processed trace summary.
    """

    return preprocess_trace(
        trace_data,
        slow_percentile=slow_percentile
    )


__all__ = [
    "extract_jaeger_spans",
    "simplify_span",
    "simplify_trace",
    "identify_critical_path",
    "detect_slow_spans",
    "detect_error_spans",
    "preprocess_trace",
    "summarize_trace",
    "create_faulty_request_trace",
]