from app.graph import build_graph


def fake_log_llm(prompt):
    return """
{
    "anomalies": [
        {
            "type": "error",
            "service": "order-service",
            "description": "request failure",
            "severity": "high",
            "evidence": "error event"
        }
    ],
    "summary": "Log failure detected",
    "confidence": 0.85
}
"""


def fake_metrics_llm(prompt):
    return """
{
    "hypothesis": "CPU and latency spike associated with incident",
    "findings": [
        {
            "metric": "cpu_usage",
            "value": 96,
            "timestamp": "2026-09-15T10:05:00",
            "service": "order-service",
            "observation": "CPU spike",
            "relevance": "high"
        }
    ],
    "confidence": 0.90
}
"""


def test_graph_executes_log_and_metrics_agents():

    graph = build_graph(
        log_llm=fake_log_llm,
        metrics_llm=fake_metrics_llm,
    )

    result = graph.invoke(
        {
            "raw_inputs": {
                "logs": [
                    {
                        "service": "order-service",
                        "message": "error event",
                    }
                ],
                "metric_anomalies": [
                    {
                        "metric": "cpu_usage",
                        "value": 96,
                        "timestamp": "2026-09-15T10:05:00",
                        "service": "order-service",
                    }
                ],
                "incident_start": "2026-09-15T10:00:00",
                "incident_end": "2026-09-15T10:10:00",
            }
        }
    )

    assert "log_analysis_agent" in result["agent_outputs"]
    assert "metrics_analysis_agent" in result["agent_outputs"]

    metrics_result = result["agent_outputs"][
        "metrics_analysis_agent"
    ]

    assert (
        metrics_result["hypothesis"]
        == "CPU and latency spike associated with incident"
    )

    assert metrics_result["confidence"] == 0.90
    assert len(metrics_result["findings"]) == 1
    assert metrics_result["findings"][0]["metric"] == "cpu_usage"
    assert metrics_result["findings"][0]["value"] == 96
