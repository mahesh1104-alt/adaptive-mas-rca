from app.metric_preprocessing import preprocess_metrics

samples = [
    {"timestamp": "2026-09-15T10:00:00Z", "metric": "cpu_usage", "value": 45.0, "service": "order-service"},
    {"timestamp": "2026-09-15T10:01:00Z", "metric": "cpu_usage", "value": 47.0, "service": "order-service"},
    {"timestamp": "2026-09-15T10:02:00Z", "metric": "cpu_usage", "value": 46.0, "service": "order-service"},
    {"timestamp": "2026-09-15T10:03:00Z", "metric": "cpu_usage", "value": 48.0, "service": "order-service"},
    {"timestamp": "2026-09-15T10:04:00Z", "metric": "cpu_usage", "value": 47.0, "service": "order-service"},
    {"timestamp": "2026-09-15T10:05:00Z", "metric": "cpu_usage", "value": 96.0, "service": "order-service"},

    {"timestamp": "2026-09-15T10:00:00Z", "metric": "latency_ms", "value": 120.0, "service": "order-service"},
    {"timestamp": "2026-09-15T10:01:00Z", "metric": "latency_ms", "value": 125.0, "service": "order-service"},
    {"timestamp": "2026-09-15T10:02:00Z", "metric": "latency_ms", "value": 118.0, "service": "order-service"},
    {"timestamp": "2026-09-15T10:03:00Z", "metric": "latency_ms", "value": 122.0, "service": "order-service"},
    {"timestamp": "2026-09-15T10:04:00Z", "metric": "latency_ms", "value": 121.0, "service": "order-service"},
    {"timestamp": "2026-09-15T10:05:00Z", "metric": "latency_ms", "value": 1250.0, "service": "order-service"},
]

result = preprocess_metrics(
    samples,
    bucket_seconds=60,
    anomaly_method="zscore",
    anomaly_threshold=2.0,
)

print("--- PREPROCESSED METRICS ---")
for item in result:
    print(item)

print("--- ANOMALIES ---")
anomalies = [item for item in result if item.get("anomaly")]
for item in anomalies:
    print(item)

print("--- ANOMALY COUNT ---")
print(len(anomalies))
