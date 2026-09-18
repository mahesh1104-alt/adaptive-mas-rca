import json

import pytest

from app.agents.metrics_analysis_agent import MetricsAnalysisAgent


def simulated_cpu_latency_spike():
    return [
        {
            "timestamp": "2026-09-14T10:00:00Z",
            "metric": "cpu_usage",
            "service": "order-service",
            "value": 42.0,
            "z_score": 0.1,
            "anomaly": False,
        },
        {
            "timestamp": "2026-09-14T10:05:00Z",
            "metric": "cpu_usage",
            "service": "order-service",
            "value": 96.0,
            "z_score": 4.2,
            "anomaly": True,
        },
        {
            "timestamp": "2026-09-14T10:05:00Z",
            "metric": "p95_latency",
            "service": "order-service",
            "value": 1250.0,
            "unit": "ms",
            "z_score": 4.8,
            "anomaly": True,
        },
        {
            "timestamp": "2026-09-14T10:06:00Z",
            "metric": "p95_latency",
            "service": "order-service",
            "value": 1380.0,
            "unit": "ms",
            "z_score": 5.1,
            "anomaly": True,
        },
    ]


def fake_llm(prompt):
    assert "cpu_usage" in prompt
    assert "96.0" in prompt
    assert "p95_latency" in prompt
    assert "1250.0" in prompt
    assert "2026-09-14T10:00:00Z" in prompt
    assert "2026-09-14T10:10:00Z" in prompt

    return json.dumps(
        {
            "hypothesis": (
                "The CPU saturation is a likely contributor "
                "to the latency increase in order-service."
            ),
            "findings": [
                {
                    "metric": "cpu_usage",
                    "value": 96.0,
                    "timestamp": "2026-09-14T10:05:00Z",
                    "service": "order-service",
                    "observation": (
                        "CPU usage increased to 96%, "
                        "with a z-score of 4.2."
                    ),
                    "relevance": (
                        "The CPU anomaly occurs within "
                        "the incident timeframe."
                    ),
                },
                {
                    "metric": "p95_latency",
                    "value": 1250.0,
                    "timestamp": "2026-09-14T10:05:00Z",
                    "service": "order-service",
                    "observation": (
                        "P95 latency increased to 1250 ms, "
                        "with a z-score of 4.8."
                    ),
                    "relevance": (
                        "The latency spike overlaps the CPU "
                        "anomaly and incident timeframe."
                    ),
                },
            ],
            "confidence": 0.91,
        }
    )


def test_metrics_analysis_agent_detects_cpu_latency_spike():
    agent = MetricsAnalysisAgent(llm=fake_llm)

    state = {
        "trace_id": "trace-metrics-001",
        "raw_inputs": {
            "metric_anomalies": simulated_cpu_latency_spike(),
            "incident_start": "2026-09-14T10:00:00Z",
            "incident_end": "2026-09-14T10:10:00Z",
        },
    }

    result = agent.run(state)

    assert "hypothesis" in result
    assert "findings" in result
    assert "confidence" in result

    assert len(result["findings"]) == 2

    assert result["findings"][0]["metric"] == "cpu_usage"
    assert result["findings"][0]["value"] == 96.0

    assert result["findings"][1]["metric"] == "p95_latency"
    assert result["findings"][1]["value"] == 1250.0

    assert "CPU" in result["hypothesis"]

    assert result["confidence"] == 0.91


def test_metrics_analysis_agent_handles_empty_metrics():
    agent = MetricsAnalysisAgent(llm=fake_llm)

    state = {
        "trace_id": "trace-metrics-002",
        "raw_inputs": {
            "metric_anomalies": [],
            "incident_start": "2026-09-14T10:00:00Z",
            "incident_end": "2026-09-14T10:10:00Z",
        },
    }

    result = agent.run(state)

    assert result["findings"] == []
    assert result["confidence"] == 0.0


def test_metrics_analysis_agent_requires_metrics_list():
    agent = MetricsAnalysisAgent(llm=fake_llm)

    state = {
        "trace_id": "trace-metrics-003",
        "raw_inputs": {
            "metric_anomalies": "invalid",
            "incident_start": "2026-09-14T10:00:00Z",
            "incident_end": "2026-09-14T10:10:00Z",
        },
    }

    with pytest.raises(ValueError):
        agent.run(state)


def test_metrics_analysis_agent_requires_llm():
    agent = MetricsAnalysisAgent()

    state = {
        "trace_id": "trace-metrics-004",
        "raw_inputs": {
            "metric_anomalies": simulated_cpu_latency_spike(),
            "incident_start": "2026-09-14T10:00:00Z",
            "incident_end": "2026-09-14T10:10:00Z",
        },
    }

    with pytest.raises(RuntimeError):
        agent.run(state)


def test_metrics_analysis_agent_rejects_invalid_llm_json():
    def invalid_llm(prompt):
        return "this is not valid JSON"

    agent = MetricsAnalysisAgent(llm=invalid_llm)

    state = {
        "trace_id": "trace-metrics-005",
        "raw_inputs": {
            "metric_anomalies": simulated_cpu_latency_spike(),
            "incident_start": "2026-09-14T10:00:00Z",
            "incident_end": "2026-09-14T10:10:00Z",
        },
    }

    with pytest.raises(json.JSONDecodeError):
        agent.run(state)
