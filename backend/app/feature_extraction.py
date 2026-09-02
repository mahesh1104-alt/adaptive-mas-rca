"""
Feature extraction and noise reduction module for Adaptive MAS RCA.

Responsibilities:
- Combine preprocessed logs, metrics, traces and source code.
- Deduplicate near-identical log messages using template extraction.
- Remove low-signal log entries while preserving important errors.
- Compact traces around RCA-relevant spans.
- Compact metrics around anomalous samples.
- Preserve relevant source-code snippets.
- Produce one feature bundle per incident.
- Measure feature-bundle size reduction.

The module is intentionally independent from FastAPI so that it can
be tested directly and reused by the RCA pipeline.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


FeatureBundle = Dict[str, Any]


# ============================================================
# LOG TEMPLATE EXTRACTION
# ============================================================

def _normalize_log_message(message: Any) -> str:
    """
    Normalize variable values in a log message.

    Common dynamic values such as IDs, numbers, UUIDs and IP
    addresses are replaced with placeholders so that otherwise
    equivalent messages can share one template.
    """

    text = str(message).strip()

    # UUIDs
    text = re.sub(
        r"\b[0-9a-fA-F]{8}-"
        r"[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{12}\b",
        "<UUID>",
        text,
    )

    # IPv4 addresses
    text = re.sub(
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "<IP>",
        text,
    )

    # Long hexadecimal identifiers
    text = re.sub(
        r"\b[0-9a-fA-F]{16,}\b",
        "<HEX>",
        text,
    )

    # Numbers
    text = re.sub(
        r"\b\d+(?:\.\d+)?\b",
        "<NUM>",
        text,
    )

    # Whitespace
    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    return text


def deduplicate_logs(
    logs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Deduplicate near-identical preprocessed log entries.

    Logs with the same service, level and normalized message are
    represented by one template with an occurrence count.

    Error and critical logs are always preserved as templates.
    """

    templates: Dict[
        tuple[str, str, str],
        Dict[str, Any],
    ] = {}

    for log in logs:
        if not isinstance(log, dict):
            continue

        service = str(
            log.get(
                "service",
                "unknown-service",
            )
        )

        level = str(
            log.get(
                "level",
                "INFO",
            )
        ).upper()

        message = _normalize_log_message(
            log.get("message", "")
        )

        key = (
            service,
            level,
            message,
        )

        if key not in templates:
            templates[key] = {
                "service": service,
                "level": level,
                "template": message,
                "error_code": log.get(
                    "error_code"
                ),
                "count": 0,
            }

        templates[key]["count"] += 1

        # Preserve an error code if one appears
        # in any duplicate occurrence.
        if (
            not templates[key].get("error_code")
            and log.get("error_code")
        ):
            templates[key]["error_code"] = (
                log.get("error_code")
            )

    return list(templates.values())


# ============================================================
# LOW-SIGNAL LOG FILTERING
# ============================================================

def remove_low_signal_logs(
    logs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Remove log templates that contain no useful diagnostic signal.

    DEBUG entries and generic informational messages are removed
    when they do not contain an error indicator.

    ERROR and CRITICAL entries are always retained.
    """

    low_signal_patterns = [
        r"^request started$",
        r"^request completed$",
        r"^health check$",
        r"^health check passed$",
        r"^heartbeat$",
        r"^connection check$",
    ]

    filtered: List[Dict[str, Any]] = []

    for log in logs:
        if not isinstance(log, dict):
            continue

        level = str(
            log.get(
                "level",
                "INFO",
            )
        ).upper()

        template = str(
            log.get(
                "template",
                "",
            )
        ).strip()

        if level in {
            "ERROR",
            "CRITICAL",
        }:
            filtered.append(log)
            continue

        is_low_signal = any(
            re.search(
                pattern,
                template,
                flags=re.IGNORECASE,
            )
            for pattern in low_signal_patterns
        )

        if not is_low_signal:
            filtered.append(log)

    return filtered


# ============================================================
# TRACE COMPACTION
# ============================================================

def compact_traces(
    trace_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Keep only RCA-relevant trace information.

    Prefer:
    - error spans
    - slow spans
    - bottleneck spans
    - failing spans
    """

    compacted: List[Dict[str, Any]] = []

    for trace in trace_data:
        if not isinstance(trace, dict):
            continue

        relevant_spans: List[Dict[str, Any]] = []

        for key in (
            "error_spans",
            "slow_spans",
        ):
            spans = trace.get(
                key,
                [],
            )

            if isinstance(spans, list):
                relevant_spans.extend(
                    span
                    for span in spans
                    if isinstance(span, dict)
                )

        for key in (
            "bottleneck_span",
            "failing_span",
        ):
            span = trace.get(key)

            if isinstance(span, dict):
                relevant_spans.append(span)

        # Deduplicate spans by span ID.
        unique_spans: Dict[
            str,
            Dict[str, Any],
        ] = {}

        for span in relevant_spans:
            span_id = str(
                span.get(
                    "span_id",
                    span.get(
                        "spanID",
                        id(span),
                    ),
                )
            )

            unique_spans[span_id] = {
                "span_id": span.get(
                    "span_id"
                ),
                "service": span.get(
                    "service"
                ),
                "operation": span.get(
                    "operation"
                ),
                "duration_ms": span.get(
                    "duration_ms"
                ),
                "status": span.get(
                    "status"
                ),
                "error": span.get(
                    "error",
                    False,
                ),
            }

        compacted.append(
            {
                "trace_id": trace.get(
                    "trace_id"
                ),
                "critical_path_duration_ms": trace.get(
                    "critical_path_duration_ms",
                    0.0,
                ),
                "spans": list(
                    unique_spans.values()
                ),
            }
        )

    return compacted


# ============================================================
# METRIC COMPACTION
# ============================================================

def compact_metrics(
    metrics: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Keep anomalous metric samples and their key identifying fields.
    """

    compacted: List[Dict[str, Any]] = []

    for metric in metrics:
        if not isinstance(metric, dict):
            continue

        if not metric.get(
            "anomaly",
            False,
        ):
            continue

        compacted.append(
            {
                "timestamp": metric.get(
                    "timestamp"
                ),
                "service": metric.get(
                    "service"
                ),
                "metric": metric.get(
                    "metric",
                    metric.get("name"),
                ),
                "value": metric.get(
                    "value"
                ),
                "unit": metric.get(
                    "unit"
                ),
                "anomaly": True,
                "z_score": metric.get(
                    "z_score"
                ),
            }
        )

    return compacted


# ============================================================
# SOURCE COMPACTION
# ============================================================

def compact_source(
    source_units: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Keep the relevant summarized source-code units.

    Source preprocessing has already selected code near the
    suspected fault, so this function keeps only the fields
    useful for downstream feature generation.
    """

    compacted: List[Dict[str, Any]] = []

    for unit in source_units:
        if not isinstance(unit, dict):
            continue

        compacted.append(
            {
                "type": unit.get(
                    "type"
                ),
                "name": unit.get(
                    "name"
                ),
                "line": unit.get(
                    "line"
                ),
                "end_line": unit.get(
                    "end_line"
                ),
                "summary": unit.get(
                    "summary"
                ),
                "code": unit.get(
                    "code"
                ),
            }
        )

    return compacted


# ============================================================
# SIZE MEASUREMENT
# ============================================================

def estimate_feature_size(
    data: Any,
) -> int:
    """
    Estimate feature-bundle size using serialized character count.

    This provides a deterministic and dependency-free measure for
    comparing raw input with the compact feature bundle.
    """

    return len(
        str(data)
    )


def calculate_reduction_ratio(
    raw_size: int,
    feature_size: int,
) -> float:
    """
    Calculate the fraction of input size removed.

    Returns a value between 0 and 1 when feature_size is smaller
    than raw_size.
    """

    if raw_size <= 0:
        return 0.0

    return max(
        0.0,
        1.0 - (
            feature_size
            / raw_size
        ),
    )


# ============================================================
# FEATURE BUNDLE
# ============================================================

def build_feature_bundle(
    incident_id: str,
    logs: List[Dict[str, Any]],
    metrics: List[Dict[str, Any]],
    traces: List[Dict[str, Any]],
    source: List[Dict[str, Any]],
) -> FeatureBundle:
    """
    Build one compact feature bundle for an incident.

    The inputs are expected to already be preprocessed by the
    corresponding preprocessing modules.
    """

    raw_input = {
        "logs": logs,
        "metrics": metrics,
        "traces": traces,
        "source": source,
    }

    raw_size = estimate_feature_size(
        raw_input
    )

    deduplicated_logs = deduplicate_logs(
        logs
    )

    filtered_logs = remove_low_signal_logs(
        deduplicated_logs
    )

    compacted_metrics = compact_metrics(
        metrics
    )

    compacted_traces = compact_traces(
        traces
    )

    compacted_source = compact_source(
        source
    )

    features = {
        "logs": filtered_logs,
        "metrics": compacted_metrics,
        "traces": compacted_traces,
        "source": compacted_source,
    }

    feature_size = estimate_feature_size(
        features
    )

    reduction_ratio = calculate_reduction_ratio(
        raw_size,
        feature_size,
    )

    return {
        "incident_id": incident_id,
        "features": features,
        "stats": {
            "raw_size": raw_size,
            "feature_size": feature_size,
            "reduction_ratio": reduction_ratio,
            "reduction_percent": (
                reduction_ratio * 100.0
            ),
        },
    }


__all__ = [
    "deduplicate_logs",
    "remove_low_signal_logs",
    "compact_traces",
    "compact_metrics",
    "compact_source",
    "estimate_feature_size",
    "calculate_reduction_ratio",
    "build_feature_bundle",
]