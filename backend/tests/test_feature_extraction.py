from app.feature_extraction import (
    build_feature_bundle,
    calculate_reduction_ratio,
    compact_metrics,
    compact_source,
    compact_traces,
    deduplicate_logs,
    estimate_feature_size,
    remove_low_signal_logs,
)


def test_deduplicate_logs():
    logs = [
        {
            "service": "inventory-service",
            "level": "ERROR",
            "message": "User 123 failed to update stock",
        },
        {
            "service": "inventory-service",
            "level": "ERROR",
            "message": "User 456 failed to update stock",
        },
        {
            "service": "inventory-service",
            "level": "ERROR",
            "message": "User 789 failed to update stock",
        },
    ]

    result = deduplicate_logs(logs)

    assert len(result) == 1
    assert result[0]["count"] == 3
    assert (
        result[0]["template"]
        == "User <NUM> failed to update stock"
    )


def test_remove_low_signal_logs():
    logs = [
        {
            "service": "inventory-service",
            "level": "INFO",
            "template": "request started",
            "count": 10,
        },
        {
            "service": "inventory-service",
            "level": "ERROR",
            "template": "database connection failed",
            "count": 1,
        },
        {
            "service": "inventory-service",
            "level": "INFO",
            "template": "stock update requested",
            "count": 2,
        },
    ]

    result = remove_low_signal_logs(logs)

    templates = [
        log["template"]
        for log in result
    ]

    assert "request started" not in templates
    assert "database connection failed" in templates
    assert "stock update requested" in templates


def test_error_logs_are_preserved():
    logs = [
        {
            "service": "inventory-service",
            "level": "ERROR",
            "template": "health check",
            "count": 1,
        },
        {
            "service": "inventory-service",
            "level": "CRITICAL",
            "template": "request started",
            "count": 1,
        },
    ]

    result = remove_low_signal_logs(logs)

    assert len(result) == 2


def test_compact_metrics_keeps_anomalies():
    metrics = [
        {
            "timestamp": "2026-09-02T10:00:00Z",
            "service": "inventory-service",
            "metric": "cpu_usage",
            "value": 95.0,
            "unit": "%",
            "anomaly": True,
            "z_score": 3.5,
        },
        {
            "timestamp": "2026-09-02T10:01:00Z",
            "service": "inventory-service",
            "metric": "cpu_usage",
            "value": 45.0,
            "unit": "%",
            "anomaly": False,
            "z_score": 0.1,
        },
    ]

    result = compact_metrics(metrics)

    assert len(result) == 1
    assert result[0]["metric"] == "cpu_usage"
    assert result[0]["anomaly"] is True
    assert result[0]["value"] == 95.0


def test_compact_traces():
    traces = [
        {
            "trace_id": "trace-001",
            "critical_path_duration_ms": 250.0,
            "error_spans": [
                {
                    "span_id": "span-error",
                    "service": "inventory-service",
                    "operation": "update_stock",
                    "duration_ms": 200.0,
                    "status": "error",
                    "error": True,
                }
            ],
            "slow_spans": [
                {
                    "span_id": "span-slow",
                    "service": "database",
                    "operation": "query",
                    "duration_ms": 180.0,
                    "status": "ok",
                    "error": False,
                }
            ],
            "bottleneck_span": {
                "span_id": "span-slow",
                "service": "database",
                "operation": "query",
                "duration_ms": 180.0,
                "status": "ok",
                "error": False,
            },
            "failing_span": {
                "span_id": "span-error",
                "service": "inventory-service",
                "operation": "update_stock",
                "duration_ms": 200.0,
                "status": "error",
                "error": True,
            },
        }
    ]

    result = compact_traces(traces)

    assert len(result) == 1
    assert result[0]["trace_id"] == "trace-001"

    span_ids = [
        span["span_id"]
        for span in result[0]["spans"]
    ]

    assert "span-error" in span_ids
    assert "span-slow" in span_ids

    # Error/bottleneck/failing spans should not be duplicated.
    assert len(span_ids) == 2


def test_compact_source():
    source = [
        {
            "type": "FunctionDef",
            "name": "update_stock",
            "line": 10,
            "end_line": 20,
            "summary": "Update the inventory quantity.",
            "code": "stock -= quantity",
        }
    ]

    result = compact_source(source)

    assert len(result) == 1
    assert result[0]["name"] == "update_stock"
    assert result[0]["summary"] == (
        "Update the inventory quantity."
    )
    assert "stock -= quantity" in result[0]["code"]


def test_estimate_feature_size():
    data = {
        "logs": [
            {
                "message": "database connection failed"
            }
        ]
    }

    size = estimate_feature_size(data)

    assert size > 0


def test_calculate_reduction_ratio():
    ratio = calculate_reduction_ratio(
        raw_size=1000,
        feature_size=400,
    )

    assert ratio == 0.6


def test_build_feature_bundle():
    logs = [
        {
            "service": "inventory-service",
            "level": "INFO",
            "message": "request started",
        },
        {
            "service": "inventory-service",
            "level": "INFO",
            "message": "request started",
        },
        {
            "service": "inventory-service",
            "level": "INFO",
            "message": "request started",
        },
        {
            "service": "inventory-service",
            "level": "ERROR",
            "message": "User 123 failed to update stock",
            "error_code": "STOCK_UPDATE_FAILED",
        },
        {
            "service": "inventory-service",
            "level": "ERROR",
            "message": "User 456 failed to update stock",
            "error_code": "STOCK_UPDATE_FAILED",
        },
    ]

    metrics = [
        {
            "timestamp": "2026-09-02T10:00:00Z",
            "service": "inventory-service",
            "metric": "cpu_usage",
            "value": 95.0,
            "unit": "%",
            "anomaly": True,
            "z_score": 3.5,
        },
        {
            "timestamp": "2026-09-02T10:01:00Z",
            "service": "inventory-service",
            "metric": "cpu_usage",
            "value": 45.0,
            "unit": "%",
            "anomaly": False,
            "z_score": 0.1,
        },
    ]

    traces = [
        {
            "trace_id": "trace-001",
            "critical_path_duration_ms": 250.0,
            "error_spans": [
                {
                    "span_id": "span-error",
                    "service": "inventory-service",
                    "operation": "update_stock",
                    "duration_ms": 200.0,
                    "status": "error",
                    "error": True,
                }
            ],
            "slow_spans": [],
            "bottleneck_span": None,
            "failing_span": {
                "span_id": "span-error",
                "service": "inventory-service",
                "operation": "update_stock",
                "duration_ms": 200.0,
                "status": "error",
                "error": True,
            },
        }
    ]

    source = [
        {
            "type": "FunctionDef",
            "name": "update_stock",
            "line": 10,
            "end_line": 20,
            "summary": "Update the inventory quantity.",
            "code": "stock -= quantity",
        }
    ]

    result = build_feature_bundle(
        incident_id="INC-001",
        logs=logs,
        metrics=metrics,
        traces=traces,
        source=source,
    )

    assert result["incident_id"] == "INC-001"

    assert "logs" in result["features"]
    assert "metrics" in result["features"]
    assert "traces" in result["features"]
    assert "source" in result["features"]

    assert result["features"]["logs"]
    assert result["features"]["metrics"]
    assert result["features"]["traces"]
    assert result["features"]["source"]

    assert result["stats"]["raw_size"] > 0
    assert result["stats"]["feature_size"] > 0

    assert (
        result["stats"]["feature_size"]
        < result["stats"]["raw_size"]
    )

    assert (
        result["stats"]["reduction_ratio"]
        > 0
    )

    assert (
        result["stats"]["reduction_percent"]
        > 0
    )

    error_logs = [
        log
        for log in result["features"]["logs"]
        if log["level"] == "ERROR"
    ]

    assert len(error_logs) == 1
    assert error_logs[0]["count"] == 2