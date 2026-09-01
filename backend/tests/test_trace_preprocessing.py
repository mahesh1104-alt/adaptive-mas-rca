"""
Tests for the trace preprocessing module.

These tests cover:
- Jaeger JSON parsing
- Span simplification
- Duration calculation
- Parent/child relationships
- Critical path detection
- Slow span detection
- Error span detection
- Faulty-request trace
- Complete preprocessing pipeline
- Incomplete/invalid input
"""

import pytest

from app.trace_preprocessing import (
    create_faulty_request_trace,
    detect_error_spans,
    detect_slow_spans,
    extract_jaeger_spans,
    identify_critical_path,
    preprocess_trace,
    simplify_span,
    simplify_trace,
)


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def sample_trace():
    """
    Simple Jaeger trace:

        API
         |
        Order
         |
      Inventory
    """

    return {
        "data": [
            {
                "traceID": "trace-001",
                "spans": [
                    {
                        "traceID": "trace-001",
                        "spanID": "span-api",
                        "operationName": "GET /orders",
                        "startTime": 1_000_000,
                        "duration": 300_000,
                        "references": [],
                        "process": {
                            "serviceName": "api-gateway"
                        },
                        "tags": []
                    },
                    {
                        "traceID": "trace-001",
                        "spanID": "span-order",
                        "operationName": "get-order",
                        "startTime": 1_050_000,
                        "duration": 200_000,
                        "references": [
                            {
                                "refType": "CHILD_OF",
                                "traceID": "trace-001",
                                "spanID": "span-api"
                            }
                        ],
                        "process": {
                            "serviceName": "order-service"
                        },
                        "tags": []
                    },
                    {
                        "traceID": "trace-001",
                        "spanID": "span-inventory",
                        "operationName": "check-inventory",
                        "startTime": 1_100_000,
                        "duration": 100_000,
                        "references": [
                            {
                                "refType": "CHILD_OF",
                                "traceID": "trace-001",
                                "spanID": "span-order"
                            }
                        ],
                        "process": {
                            "serviceName": "inventory-service"
                        },
                        "tags": []
                    }
                ]
            }
        ]
    }


@pytest.fixture
def faulty_trace():
    """
    Deterministic simulated faulty request.
    """

    return create_faulty_request_trace()


# ============================================================
# PARSING TESTS
# ============================================================

def test_extract_jaeger_spans(sample_trace):
    """
    Verify that Jaeger query JSON is converted into a span list.
    """

    spans = extract_jaeger_spans(
        sample_trace
    )

    assert len(spans) == 3
    assert spans[0]["spanID"] == "span-api"
    assert spans[1]["spanID"] == "span-order"
    assert spans[2]["spanID"] == "span-inventory"


def test_extract_empty_trace():
    """
    Empty trace input should return an empty list.
    """

    assert extract_jaeger_spans({}) == []
    assert extract_jaeger_spans(None) == []
    assert extract_jaeger_spans([]) == []


def test_extract_direct_span_list():
    """
    Verify that a direct list of spans is supported.
    """

    spans = [
        {
            "spanID": "span-1",
            "operationName": "operation-1"
        },
        {
            "spanID": "span-2",
            "operationName": "operation-2"
        }
    ]

    result = extract_jaeger_spans(
        spans
    )

    assert len(result) == 2


# ============================================================
# SPAN SIMPLIFICATION TESTS
# ============================================================

def test_simplify_span(sample_trace):
    """
    Verify service, operation, duration and trace fields.
    """

    raw_span = sample_trace["data"][0]["spans"][0]

    result = simplify_span(
        raw_span
    )

    assert result["span_id"] == "span-api"
    assert result["trace_id"] == "trace-001"
    assert result["service"] == "api-gateway"
    assert result["operation"] == "GET /orders"

    # Jaeger duration is microseconds.
    assert result["duration_us"] == 300_000

    # Simplified representation is milliseconds.
    assert result["duration_ms"] == 300.0

    assert result["error"] is False


def test_simplify_trace(sample_trace):
    """
    Verify that all spans are simplified.
    """

    result = simplify_trace(
        sample_trace
    )

    assert len(result) == 3

    assert result[0]["service"] == "api-gateway"
    assert result[1]["service"] == "order-service"
    assert result[2]["service"] == "inventory-service"


# ============================================================
# PARENT/CHILD TESTS
# ============================================================

def test_parent_relationships(sample_trace):
    """
    Verify parent-child relationships are extracted correctly.
    """

    spans = simplify_trace(
        sample_trace
    )

    assert spans[0]["parent_span_id"] is None

    assert spans[1]["parent_span_id"] == (
        "span-api"
    )

    assert spans[2]["parent_span_id"] == (
        "span-order"
    )


# ============================================================
# CRITICAL PATH TESTS
# ============================================================

def test_critical_path(sample_trace):
    """
    Verify the longest parent/child path.
    """

    spans = simplify_trace(
        sample_trace
    )

    critical_path = identify_critical_path(
        spans
    )

    assert len(critical_path) == 3

    assert [
        span["span_id"]
        for span in critical_path
    ] == [
        "span-api",
        "span-order",
        "span-inventory"
    ]


def test_critical_path_chooses_longest_branch():
    """
    Verify that the algorithm selects the longest child branch.

             root
             /  \
           fast slow
    """

    spans = [
        {
            "span_id": "root",
            "parent_span_id": None,
            "duration_ms": 10.0
        },
        {
            "span_id": "fast",
            "parent_span_id": "root",
            "duration_ms": 20.0
        },
        {
            "span_id": "slow",
            "parent_span_id": "root",
            "duration_ms": 100.0
        }
    ]

    result = identify_critical_path(
        spans
    )

    assert [
        span["span_id"]
        for span in result
    ] == [
        "root",
        "slow"
    ]


# ============================================================
# SLOW SPAN TESTS
# ============================================================

def test_slow_span_detection():
    """
    Verify percentile-based slow span detection.
    """

    spans = [
        {
            "span_id": "span-1",
            "duration_ms": 10.0
        },
        {
            "span_id": "span-2",
            "duration_ms": 20.0
        },
        {
            "span_id": "span-3",
            "duration_ms": 30.0
        },
        {
            "span_id": "span-4",
            "duration_ms": 1000.0
        }
    ]

    result = detect_slow_spans(
        spans,
        percentile=75
    )

    slow_spans = [
        span
        for span in result
        if span["slow"]
    ]

    assert len(slow_spans) >= 1

    assert slow_spans[-1]["span_id"] == (
        "span-4"
    )


def test_slow_span_contains_threshold():
    """
    Every processed span should contain the calculated threshold.
    """

    spans = [
        {
            "span_id": "span-1",
            "duration_ms": 10.0
        },
        {
            "span_id": "span-2",
            "duration_ms": 20.0
        }
    ]

    result = detect_slow_spans(
        spans,
        percentile=95
    )

    assert all(
        "slow_threshold_ms" in span
        for span in result
    )


# ============================================================
# ERROR DETECTION TESTS
# ============================================================

def test_error_span_detection():
    """
    Verify error spans are filtered correctly.
    """

    spans = [
        {
            "span_id": "success-span",
            "error": False
        },
        {
            "span_id": "error-span",
            "error": True
        }
    ]

    result = detect_error_spans(
        spans
    )

    assert len(result) == 1
    assert result[0]["span_id"] == (
        "error-span"
    )


def test_http_500_is_detected_as_error():
    """
    HTTP 500 should mark a span as an error.
    """

    span = {
        "traceID": "trace-error",
        "spanID": "span-error",
        "operationName": "GET /inventory",
        "startTime": 1_000_000,
        "duration": 500_000,
        "process": {
            "serviceName": "inventory-service"
        },
        "tags": [
            {
                "key": "http.status_code",
                "type": "int",
                "value": 500
            }
        ]
    }

    result = simplify_span(
        span
    )

    assert result["error"] is True
    assert result["status"] == "ERROR"


# ============================================================
# FAULTY REQUEST TESTS
# ============================================================

def test_faulty_request_trace(faulty_trace):
    """
    Verify the simulated faulty request contains
    the expected failing inventory span.
    """

    result = preprocess_trace(
        faulty_trace
    )

    assert result["trace_id"] == (
        "faulty-trace-001"
    )

    assert result["span_count"] == 4

    assert len(
        result["error_spans"]
    ) >= 1

    failing_span = result[
        "failing_span"
    ]

    assert failing_span is not None

    assert failing_span["service"] == (
        "inventory-service"
    )

    assert failing_span["error"] is True


def test_faulty_request_identifies_bottleneck(
    faulty_trace
):
    """
    Verify that the slow inventory span is highlighted
    as the bottleneck on the critical path.
    """

    result = preprocess_trace(
        faulty_trace,
        slow_percentile=75
    )

    bottleneck = result[
        "bottleneck_span"
    ]

    assert bottleneck is not None

    assert bottleneck["service"] == (
        "inventory-service"
    )

    assert bottleneck["duration_ms"] == 350.0


# ============================================================
# COMPLETE PIPELINE TEST
# ============================================================

def test_complete_preprocessing_pipeline(
    sample_trace
):
    """
    Verify the complete trace preprocessing pipeline.
    """

    result = preprocess_trace(
        sample_trace,
        slow_percentile=95
    )

    assert result["trace_id"] == (
        "trace-001"
    )

    assert result["span_count"] == 3

    assert len(
        result["spans"]
    ) == 3

    assert len(
        result["critical_path"]
    ) == 3

    assert result[
        "critical_path_duration_ms"
    ] == 600.0

    assert "slow_spans" in result

    assert "error_spans" in result

    assert "bottleneck_span" in result

    assert result[
        "bottleneck_span"
    ]["span_id"] == "span-api"


# ============================================================
# INVALID / INCOMPLETE INPUT TESTS
# ============================================================

def test_empty_trace_returns_safe_result():
    """
    Incomplete input should not crash the pipeline.
    """

    result = preprocess_trace({})

    assert result["span_count"] == 0
    assert result["spans"] == []
    assert result["critical_path"] == []
    assert result["slow_spans"] == []
    assert result["error_spans"] == []
    assert result["bottleneck_span"] is None
    assert result["failing_span"] is None


def test_invalid_trace_returns_safe_result():
    """
    Non-dictionary/non-list input should be handled safely.
    """

    result = preprocess_trace(
        "not-a-trace"
    )

    assert result["span_count"] == 0
    assert result["spans"] == []


# ============================================================
# MISSING FIELD TEST
# ============================================================

def test_missing_optional_span_fields_are_safe():
    """
    Verify that a minimal span can still be simplified.
    """

    span = {
        "spanID": "minimal-span",
        "operationName": "minimal-operation",
        "duration": 1000
    }

    result = simplify_span(
        span
    )

    assert result["span_id"] == (
        "minimal-span"
    )

    assert result["operation"] == (
        "minimal-operation"
    )

    assert result["duration_ms"] == 1.0

    assert result["service"] == (
        "unknown-service"
    )

    assert result["error"] is False