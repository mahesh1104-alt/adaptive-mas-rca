import pytest
from app.metric_preprocessing import (
    aggregate_metrics,
    convert_counter_to_rates,
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


def test_normalize_unit_same_unit():
    result = normalize_unit(25, "ms", "ms")

    assert result == 25.0


def test_normalize_unit_missing_units():
    result = normalize_unit(25, None, None)

    assert result == 25.0


def test_normalize_unit_invalid_source_unit():
    with pytest.raises(ValueError):
        normalize_unit(10, "invalid", "s")


def test_normalize_unit_invalid_target_unit():
    with pytest.raises(ValueError):
        normalize_unit(10, "ms", "invalid")


def test_aggregate_metrics_empty_input():
    result = aggregate_metrics([])

    assert result == []


def test_aggregate_metrics_invalid_bucket_seconds():
    with pytest.raises(ValueError):
        aggregate_metrics(
            [
                {
                    "timestamp": "2026-08-01T10:00:00Z",
                    "metric": "cpu",
                    "value": 50,
                }
            ],
            bucket_seconds=0,
        )


def test_aggregate_metrics_different_aggregations():
    samples = [
        {
            "timestamp": "2026-08-01T10:00:05Z",
            "metric": "cpu",
            "value": 20,
        },
        {
            "timestamp": "2026-08-01T10:00:25Z",
            "metric": "cpu",
            "value": 40,
        },
    ]

    assert aggregate_metrics(
        samples,
        aggregation="sum",
    )[0]["value"] == 60

    assert aggregate_metrics(
        samples,
        aggregation="min",
    )[0]["value"] == 20

    assert aggregate_metrics(
        samples,
        aggregation="max",
    )[0]["value"] == 40


def test_aggregate_metrics_invalid_aggregation():
    samples = [
        {
            "timestamp": "2026-08-01T10:00:00Z",
            "metric": "cpu",
            "value": 50,
        }
    ]

    with pytest.raises(ValueError):
        aggregate_metrics(
            samples,
            aggregation="median",
        )


def test_zscore_empty_input():
    result = detect_zscore_anomalies([])

    assert result == []


def test_zscore_invalid_threshold():
    samples = [
        {"timestamp": "1", "metric": "cpu", "value": 10},
        {"timestamp": "2", "metric": "cpu", "value": 20},
    ]

    with pytest.raises(ValueError):
        detect_zscore_anomalies(
            samples,
            threshold=0,
        )


def test_zscore_constant_values():
    samples = [
        {"timestamp": "1", "metric": "cpu", "value": 50},
        {"timestamp": "2", "metric": "cpu", "value": 50},
        {"timestamp": "3", "metric": "cpu", "value": 50},
    ]

    result = detect_zscore_anomalies(samples)

    assert all(item["z_score"] == 0 for item in result)
    assert all(item["anomaly"] is False for item in result)


def test_threshold_minimum_detection():
    samples = [
        {"metric": "cpu", "value": 20},
        {"metric": "cpu", "value": 50},
        {"metric": "cpu", "value": 80},
    ]

    result = detect_threshold_anomalies(
        samples,
        minimum=30,
    )

    assert result[0]["anomaly"] is True
    assert result[1]["anomaly"] is False
    assert result[2]["anomaly"] is False


def test_threshold_requires_limit():
    samples = [
        {"metric": "cpu", "value": 50},
    ]

    with pytest.raises(ValueError):
        detect_threshold_anomalies(samples)


def test_normalize_metric_units_without_unit():
    samples = [
        {
            "timestamp": "2026-08-01T10:00:00Z",
            "metric": "latency",
            "value": 100,
        }
    ]

    result = normalize_metric_units(
        samples,
        target_unit="s",
    )

    assert result[0]["value"] == 100.0
    assert result[0]["unit"] == "s"


def test_preprocess_metrics_empty_input():
    result = preprocess_metrics([])

    assert result == []


def test_preprocess_metrics_threshold_method():
    samples = [
        {
            "timestamp": "2026-08-01T10:00:00Z",
            "metric": "cpu",
            "value": 50,
        },
        {
            "timestamp": "2026-08-01T10:01:00Z",
            "metric": "cpu",
            "value": 95,
        },
    ]

    result = preprocess_metrics(
        samples,
        bucket_seconds=60,
        anomaly_method="threshold",
        maximum=90,
    )

    assert len(result) == 2
    assert result[0]["anomaly"] is False
    assert result[1]["anomaly"] is True


def test_preprocess_metrics_invalid_anomaly_method():
    samples = [
        {
            "timestamp": "2026-08-01T10:00:00Z",
            "metric": "cpu",
            "value": 50,
        }
    ]

    with pytest.raises(ValueError):
        preprocess_metrics(
            samples,
            anomaly_method="invalid",
        )
def test_complete_pipeline_with_cpu_and_latency_spikes():
    samples = [
        {"timestamp": "2026-08-01T10:00:01Z", "metric": "cpu_usage", "service": "order-service", "value": 45},
        {"timestamp": "2026-08-01T10:01:01Z", "metric": "cpu_usage", "service": "order-service", "value": 47},
        {"timestamp": "2026-08-01T10:02:01Z", "metric": "cpu_usage", "service": "order-service", "value": 46},
        {"timestamp": "2026-08-01T10:03:01Z", "metric": "cpu_usage", "service": "order-service", "value": 48},
        {"timestamp": "2026-08-01T10:04:01Z", "metric": "cpu_usage", "service": "order-service", "value": 47},
        {"timestamp": "2026-08-01T10:05:01Z", "metric": "cpu_usage", "service": "order-service", "value": 96},

        {"timestamp": "2026-08-01T10:00:01Z", "metric": "latency_ms", "service": "order-service", "value": 120},
        {"timestamp": "2026-08-01T10:01:01Z", "metric": "latency_ms", "service": "order-service", "value": 125},
        {"timestamp": "2026-08-01T10:02:01Z", "metric": "latency_ms", "service": "order-service", "value": 118},
        {"timestamp": "2026-08-01T10:03:01Z", "metric": "latency_ms", "service": "order-service", "value": 122},
        {"timestamp": "2026-08-01T10:04:01Z", "metric": "latency_ms", "service": "order-service", "value": 121},
        {"timestamp": "2026-08-01T10:05:01Z", "metric": "latency_ms", "service": "order-service", "value": 1250},
    ]

    result = preprocess_metrics(
        samples,
        bucket_seconds=60,
        anomaly_method="zscore",
        anomaly_threshold=2.0,
    )

    anomalies = [
        item
        for item in result
        if item["anomaly"]
    ]

    assert len(anomalies) == 2

    cpu_spikes = [
        item
        for item in anomalies
        if item["metric"] == "cpu_usage"
    ]

    latency_spikes = [
        item
        for item in anomalies
        if item["metric"] == "latency_ms"
    ]

    assert len(cpu_spikes) == 1
    assert cpu_spikes[0]["value"] == 96
    assert cpu_spikes[0]["z_score"] > 2.0

    assert len(latency_spikes) == 1
    assert latency_spikes[0]["value"] == 1250
    assert latency_spikes[0]["z_score"] > 2.0

def test_convert_counter_to_rates():
    samples = [
        {
            "timestamp": "2026-08-01T10:00:00Z",
            "metric": "requests_total",
            "service": "order-service",
            "value": 10,
        },
        {
            "timestamp": "2026-08-01T10:00:10Z",
            "metric": "requests_total",
            "service": "order-service",
            "value": 30,
        },
        {
            "timestamp": "2026-08-01T10:00:20Z",
            "metric": "requests_total",
            "service": "order-service",
            "value": 50,
        },
    ]

    result = convert_counter_to_rates(samples)

    assert len(result) == 2
    assert result[0]["value"] == 2.0
    assert result[1]["value"] == 2.0
    assert result[0]["rate"] == 2.0
    assert result[1]["rate"] == 2.0

def test_convert_counter_to_rates_handles_reset():
    samples = [
        {
            "timestamp": "2026-08-01T10:00:00Z",
            "metric": "requests_total",
            "service": "order-service",
            "value": 90,
        },
        {
            "timestamp": "2026-08-01T10:00:10Z",
            "metric": "requests_total",
            "service": "order-service",
            "value": 100,
        },
        {
            "timestamp": "2026-08-01T10:00:20Z",
            "metric": "requests_total",
            "service": "order-service",
            "value": 5,
        },
    ]

    result = convert_counter_to_rates(samples)

    assert len(result) == 2
    assert result[0]["value"] == 1.0
    assert result[1]["value"] == 0.5