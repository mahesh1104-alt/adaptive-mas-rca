from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ============================================================
# UNIT CONVERSION
# ============================================================

UNIT_FACTORS = {
    # Time
    "ns": 1e-9,
    "nanoseconds": 1e-9,

    "us": 1e-6,
    "µs": 1e-6,
    "microseconds": 1e-6,

    "ms": 1e-3,
    "milliseconds": 1e-3,

    "s": 1.0,
    "sec": 1.0,
    "seconds": 1.0,

    # Bytes
    "b": 1.0,
    "bytes": 1.0,

    "kb": 1024.0,
    "kib": 1024.0,

    "mb": 1024.0 * 1024.0,
    "mib": 1024.0 * 1024.0,

    "gb": 1024.0 * 1024.0 * 1024.0,
    "gib": 1024.0 * 1024.0 * 1024.0,
}


def normalize_unit(
    value: float,
    from_unit: Optional[str],
    to_unit: Optional[str],
) -> float:
    """
    Convert a metric value between supported units.
    """

    if not from_unit or not to_unit:
        return float(value)

    source = from_unit.strip().lower()
    target = to_unit.strip().lower()

    if source == target:
        return float(value)

    if source not in UNIT_FACTORS:
        raise ValueError(
            f"Unsupported source unit: {from_unit}"
        )

    if target not in UNIT_FACTORS:
        raise ValueError(
            f"Unsupported target unit: {to_unit}"
        )

    value_in_base_unit = (
        float(value) * UNIT_FACTORS[source]
    )

    return (
        value_in_base_unit
        / UNIT_FACTORS[target]
    )


# ============================================================
# TIMESTAMP HELPERS
# ============================================================

def parse_timestamp(timestamp: Any) -> datetime:
    """
    Convert an ISO timestamp into a timezone-aware datetime.
    """

    if isinstance(timestamp, datetime):
        result = timestamp

    else:
        value = str(timestamp).strip()

        if value.endswith("Z"):
            value = value[:-1] + "+00:00"

        result = datetime.fromisoformat(value)

    if result.tzinfo is None:
        result = result.replace(
            tzinfo=timezone.utc
        )

    return result.astimezone(timezone.utc)


def minute_bucket(timestamp: Any) -> datetime:
    """
    Place a timestamp into a one-minute bucket.
    """

    parsed = parse_timestamp(timestamp)

    return parsed.replace(
        second=0,
        microsecond=0,
    )


# ============================================================
# RESAMPLING / AGGREGATION
# ============================================================

def aggregate_metrics(
    samples: List[Dict[str, Any]],
    bucket_seconds: int = 60,
    aggregation: str = "mean",
) -> List[Dict[str, Any]]:
    """
    Aggregate metric samples into fixed time buckets.

    Expected input:

    {
        "timestamp": "...",
        "metric": "cpu_usage",
        "value": 75.0
    }

    Optional:
        "service"
        "unit"
        "labels"
    """

    if not samples:
        return []

    if bucket_seconds <= 0:
        raise ValueError(
            "bucket_seconds must be greater than zero"
        )

    aggregation = aggregation.lower()

    if aggregation not in {
        "mean",
        "sum",
        "min",
        "max",
    }:
        raise ValueError(
            "aggregation must be mean, sum, min, or max"
        )

    buckets = defaultdict(list)

    for sample in samples:
        timestamp = parse_timestamp(
            sample["timestamp"]
        )

        bucket_start = timestamp.replace(
            second=(
                timestamp.second
                // bucket_seconds
            ) * bucket_seconds,
            microsecond=0,
        )

        key = (
            sample.get("metric")
            or sample.get("name"),
            sample.get("service"),
            bucket_start,
        )

        buckets[key].append(
            float(sample["value"])
        )

    result = []

    for (
        metric_name,
        service,
        bucket_start,
    ), values in sorted(
        buckets.items(),
        key=lambda item: item[0][2],
    ):

        if aggregation == "mean":
            aggregated_value = (
                sum(values) / len(values)
            )

        elif aggregation == "sum":
            aggregated_value = sum(values)

        elif aggregation == "min":
            aggregated_value = min(values)

        else:
            aggregated_value = max(values)

        result.append(
            {
                "timestamp": bucket_start.isoformat().replace(
                    "+00:00",
                    "Z",
                ),
                "metric": metric_name,
                "service": service,
                "value": aggregated_value,
                "sample_count": len(values),
            }
        )

    return result


PROMETHEUS_COUNTER_METRICS = {
    "flask_http_request_total",
    "flask_http_request_duration_seconds_count",
    "flask_http_request_duration_seconds_sum",
}

def convert_counter_to_rates(
    samples: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Convert cumulative counter samples into per-second rates.
    """
    if not samples:
        return []

    samples = [
        sample
        for sample in samples
        if (
            sample.get("metric") or sample.get("name")
        ) in PROMETHEUS_COUNTER_METRICS or str(sample.get("metric") or sample.get("name") or "").endswith("_total")
    ]

    groups = defaultdict(list)

    for sample in samples:
        key = (
            sample.get("metric") or sample.get("name"),
            sample.get("service"),
        )
        groups[key].append(sample)

    results = []

    for group_samples in groups.values():
        group_samples = sorted(
            group_samples,
            key=lambda sample: parse_timestamp(sample["timestamp"]),
        )

        for previous, current in zip(
            group_samples,
            group_samples[1:],
        ):
            previous_value = float(previous["value"])
            current_value = float(current["value"])

            previous_time = parse_timestamp(
                previous["timestamp"]
            )
            current_time = parse_timestamp(
                current["timestamp"]
            )

            elapsed_seconds = (
                current_time - previous_time
            ).total_seconds()

            if elapsed_seconds <= 0:
                continue

            delta = current_value - previous_value

            # Handle normal counter resets.
            if delta < 0:
                delta = current_value

            enriched = dict(current)
            enriched["value"] = delta / elapsed_seconds
            enriched["rate"] = enriched["value"]
            enriched["anomaly"] = False

            results.append(enriched)

    return results


# ============================================================
# Z-SCORE ANOMALY DETECTION
# ============================================================

def detect_zscore_anomalies(
    samples: List[Dict[str, Any]],
    threshold: float = 3.0,
) -> List[Dict[str, Any]]:
    """
    Detect anomalies using z-score independently for each
    metric/service group.

    z = (value - mean) / standard deviation

    A sample is anomalous when:

        abs(z) >= threshold
    """

    if not samples:
        return []

    if threshold <= 0:
        raise ValueError(
            "threshold must be greater than zero"
        )

    groups = defaultdict(list)

    for sample in samples:
        key = (
            sample.get("metric")
            or sample.get("name"),
            sample.get("service"),
        )

        groups[key].append(sample)

    results = []

    for group_samples in groups.values():

        values = [
            float(sample["value"])
            for sample in group_samples
        ]

        mean = sum(values) / len(values)

        variance = sum(
            (value - mean) ** 2
            for value in values
        ) / len(values)

        stddev = variance ** 0.5

        for sample in group_samples:
            value = float(sample["value"])

            if stddev == 0:
                z_score = 0.0
            else:
                z_score = (
                    (value - mean)
                    / stddev
                )

            enriched = dict(sample)

            enriched["z_score"] = z_score
            enriched["anomaly"] = (
                abs(z_score) >= threshold
            )

            results.append(enriched)

    return results

# ============================================================
# STATIC THRESHOLD DETECTION
# ============================================================

def detect_threshold_anomalies(
    samples: List[Dict[str, Any]],
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Detect anomalies using static minimum/maximum
    thresholds.
    """

    if minimum is None and maximum is None:
        raise ValueError(
            "At least one threshold is required"
        )

    results = []

    for sample in samples:
        value = float(sample["value"])

        below_minimum = (
            minimum is not None
            and value < minimum
        )

        above_maximum = (
            maximum is not None
            and value > maximum
        )

        enriched = dict(sample)

        enriched["anomaly"] = (
            below_minimum
            or above_maximum
        )

        results.append(enriched)

    return results


# ============================================================
# METRIC UNIT NORMALIZATION
# ============================================================

def normalize_metric_units(
    samples: List[Dict[str, Any]],
    target_unit: str,
) -> List[Dict[str, Any]]:
    """
    Normalize all metric samples to target_unit.
    """

    results = []

    for sample in samples:
        enriched = dict(sample)

        source_unit = sample.get("unit")

        enriched["value"] = normalize_unit(
            sample["value"],
            source_unit,
            target_unit,
        )

        enriched["unit"] = target_unit

        results.append(enriched)

    return results


# ============================================================
# COMPLETE METRIC PREPROCESSING
# ============================================================

def preprocess_metrics(
    samples: List[Dict[str, Any]],
    bucket_seconds: int = 60,
    aggregation: str = "mean",
    anomaly_method: str = "zscore",
    anomaly_threshold: float = 3.0,
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
    target_unit: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Complete metrics preprocessing pipeline.

    Steps:

    1. Normalize units.
    2. Aggregate into time buckets.
    3. Detect anomalies.

    Returns structured metric records.
    """

    if not samples:
        return []

    working_samples = samples

    counter_samples = [
        sample
        for sample in working_samples
        if (
            sample.get("metric") or sample.get("name")
        ) in PROMETHEUS_COUNTER_METRICS or str(sample.get("metric") or sample.get("name") or "").endswith("_total")
    ]

    gauge_samples = [
        sample
        for sample in working_samples
        if (
            sample.get("metric") or sample.get("name")
        ) not in PROMETHEUS_COUNTER_METRICS
    ]

    if counter_samples:
        counter_samples = convert_counter_to_rates(counter_samples)

    working_samples = gauge_samples + counter_samples

    if target_unit:
        working_samples = normalize_metric_units(
            working_samples,
            target_unit,
        )

    aggregated = aggregate_metrics(
        working_samples,
        bucket_seconds=bucket_seconds,
        aggregation=aggregation,
    )

    anomaly_method = anomaly_method.lower()

    if anomaly_method == "zscore":
        return detect_zscore_anomalies(
            aggregated,
            threshold=anomaly_threshold,
        )

    if anomaly_method == "threshold":
        return detect_threshold_anomalies(
            aggregated,
            minimum=minimum,
            maximum=maximum,
        )

    raise ValueError(
        "anomaly_method must be 'zscore' "
        "or 'threshold'"
    )
