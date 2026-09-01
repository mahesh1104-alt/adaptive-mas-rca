from app.metric_preprocessing import (
    aggregate_metrics,
    detect_threshold_anomalies,
    detect_zscore_anomalies,
    normalize_unit,
    normalize_metric_units,
    preprocess_metrics,
)


def test_minute_aggregation():
    samples = [
        {
            "timestamp": "2026-08-01T10:00:05Z",
            "metric": "cpu_usage",
            "service": "inventory-service",
            "value": 40,
        },
        {
            "timestamp": "2026-08-01T10:00:20Z",
            "metric": "cpu_usage",
            "service": "inventory-service",
            "value": 50,
        },
        {
            "timestamp": "2026-08-01T10:00:45Z",
            "metric": "cpu_usage",
            "service": "inventory-service",
            "value": 60,
        },
    ]

    result = aggregate_metrics(samples)

    assert len(result) == 1
    assert result[0]["metric"] == "cpu_usage"
    assert result[0]["service"] == "inventory-service"
    assert result[0]["value"] == 50
    assert result[0]["sample_count"] == 3


def test_multiple_minute_buckets():
    samples = [
        {
            "timestamp": "2026-08-01T10:00:10Z",
            "metric": "latency",
            "value": 100,
        },
        {
            "timestamp": "2026-08-01T10:00:50Z",
            "metric": "latency",
            "value": 120,
        },
        {
            "timestamp": "2026-08-01T10:01:10Z",
            "metric": "latency",
            "value": 200,
        },
    ]

    result = aggregate_metrics(samples)

    assert len(result) == 2
    assert result[0]["value"] == 110
    assert result[1]["value"] == 200


def test_zscore_anomaly_detection():
    samples = [
        {"timestamp": "1", "metric": "cpu", "value": 40},
        {"timestamp": "2", "metric": "cpu", "value": 41},
        {"timestamp": "3", "metric": "cpu", "value": 42},
        {"timestamp": "4", "metric": "cpu", "value": 41},
        {"timestamp": "5", "metric": "cpu", "value": 40},
        {"timestamp": "6", "metric": "cpu", "value": 42},
        {"timestamp": "7", "metric": "cpu", "value": 95},
    ]

    result = detect_zscore_anomalies(
        samples,
        threshold=2.0,
    )

    anomalies = [
        item
        for item in result
        if item["anomaly"]
    ]

    assert len(anomalies) == 1
    assert anomalies[0]["value"] == 95


def test_static_threshold_detection():
    samples = [
        {"metric": "cpu", "value": 50},
        {"metric": "cpu", "value": 75},
        {"metric": "cpu", "value": 95},
    ]

    result = detect_threshold_anomalies(
        samples,
        maximum=90,
    )

    assert result[0]["anomaly"] is False
    assert result[1]["anomaly"] is False
    assert result[2]["anomaly"] is True


def test_milliseconds_to_seconds():
    result = normalize_unit(
        1500,
        "ms",
        "s",
    )

    assert result == 1.5


def test_seconds_to_milliseconds():
    result = normalize_unit(
        2,
        "s",
        "ms",
    )

    assert result == 2000


def test_megabytes_to_bytes():
    result = normalize_unit(
        1,
        "MB",
        "bytes",
    )

    assert result == 1024 * 1024


def test_metric_unit_normalization():
    samples = [
        {
            "timestamp": "2026-08-01T10:00:00Z",
            "metric": "latency",
            "value": 1000,
            "unit": "ms",
        },
        {
            "timestamp": "2026-08-01T10:01:00Z",
            "metric": "latency",
            "value": 2,
            "unit": "s",
        },
    ]

    result = normalize_metric_units(
        samples,
        target_unit="s",
    )

    assert result[0]["value"] == 1
    assert result[1]["value"] == 2
    assert result[0]["unit"] == "s"
    assert result[1]["unit"] == "s"


def test_complete_metric_preprocessing_pipeline():
    samples = [
        {
            "timestamp": "2026-08-01T10:00:05Z",
            "metric": "cpu_usage",
            "service": "inventory-service",
            "value": 40,
        },
        {
            "timestamp": "2026-08-01T10:00:20Z",
            "metric": "cpu_usage",
            "service": "inventory-service",
            "value": 42,
        },
        {
            "timestamp": "2026-08-01T10:00:40Z",
            "metric": "cpu_usage",
            "service": "inventory-service",
            "value": 41,
        },
    ]

    result = preprocess_metrics(
        samples,
        bucket_seconds=60,
        anomaly_method="zscore",
        anomaly_threshold=2.0,
    )

    assert len(result) == 1
    assert result[0]["metric"] == "cpu_usage"
    assert result[0]["service"] == "inventory-service"
    assert result[0]["value"] == 41
    assert "z_score" in result[0]
    assert "anomaly" in result[0]


def test_complete_pipeline_with_injected_cpu_spike():
    samples = [
        {
            "timestamp": "2026-08-01T10:00:01Z",
            "metric": "cpu_usage",
            "service": "inventory-service",
            "value": 40,
        },
        {
            "timestamp": "2026-08-01T10:01:01Z",
            "metric": "cpu_usage",
            "service": "inventory-service",
            "value": 41,
        },
        {
            "timestamp": "2026-08-01T10:02:01Z",
            "metric": "cpu_usage",
            "service": "inventory-service",
            "value": 42,
        },
        {
            "timestamp": "2026-08-01T10:03:01Z",
            "metric": "cpu_usage",
            "service": "inventory-service",
            "value": 40,
        },
        {
            "timestamp": "2026-08-01T10:04:01Z",
            "metric": "cpu_usage",
            "service": "inventory-service",
            "value": 43,
        },
        {
            "timestamp": "2026-08-01T10:05:01Z",
            "metric": "cpu_usage",
            "service": "inventory-service",
            "value": 95,
        },
        {
            "timestamp": "2026-08-01T10:06:01Z",
            "metric": "cpu_usage",
            "service": "inventory-service",
            "value": 41,
        },
    ]

    result = preprocess_metrics(
        samples,
        bucket_seconds=60,
        anomaly_method="zscore",
        anomaly_threshold=2.0,
    )

    spike_records = [
        item
        for item in result
        if item["value"] == 95
    ]

    assert len(spike_records) == 1
    assert spike_records[0]["anomaly"] is True
    assert spike_records[0]["z_score"] > 2.0