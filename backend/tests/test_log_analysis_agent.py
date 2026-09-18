import json

import pytest

from app.agents.log_analysis_agent import LogAnalysisAgent


def simulated_fault_logs():
    return [
        {
            "timestamp": "2026-09-14T10:00:00Z",
            "service": "order-service",
            "level": "INFO",
            "message": "Order request received",
        },
        {
            "timestamp": "2026-09-14T10:00:01Z",
            "service": "order-service",
            "level": "ERROR",
            "message": "Database connection timeout",
            "error_code": "DB_TIMEOUT",
        },
        {
            "timestamp": "2026-09-14T10:00:02Z",
            "service": "order-service",
            "level": "ERROR",
            "message": "Database connection timeout",
            "error_code": "DB_TIMEOUT",
        },
        {
            "timestamp": "2026-09-14T10:00:03Z",
            "service": "order-service",
            "level": "ERROR",
            "message": "Failed to acquire database connection",
            "error_code": "DB_POOL_EXHAUSTED",
        },
    ]


def fake_llm(prompt):
    assert "Database connection timeout" in prompt
    assert "DB_POOL_EXHAUSTED" in prompt

    return json.dumps(
        {
            "anomalies": [
                {
                    "type": "database_failure",
                    "service": "order-service",
                    "description": (
                        "Repeated database connection failures "
                        "were detected."
                    ),
                    "severity": "high",
                    "evidence": (
                        "DB_TIMEOUT and DB_POOL_EXHAUSTED "
                        "errors occur repeatedly."
                    ),
                }
            ],
            "summary": (
                "The order-service is experiencing repeated "
                "database connection failures."
            ),
            "confidence": 0.94,
        }
    )


def test_log_analysis_agent_detects_fault():
    agent = LogAnalysisAgent(llm=fake_llm)

    state = {
        "trace_id": "trace-log-001",
        "raw_inputs": {
            "logs": simulated_fault_logs()
        },
    }

    result = agent.run(state)

    assert "anomalies" in result
    assert "summary" in result
    assert "confidence" in result

    assert len(result["anomalies"]) == 1

    anomaly = result["anomalies"][0]

    assert anomaly["service"] == "order-service"
    assert anomaly["severity"] == "high"

    assert "database" in anomaly["description"].lower()

    assert result["confidence"] == 0.94


def test_log_analysis_agent_handles_empty_logs():
    agent = LogAnalysisAgent(llm=fake_llm)

    state = {
        "trace_id": "trace-log-002",
        "raw_inputs": {
            "logs": []
        },
    }

    result = agent.run(state)

    assert result["anomalies"] == []
    assert result["confidence"] == 0.0


def test_log_analysis_agent_requires_logs_list():
    agent = LogAnalysisAgent(llm=fake_llm)

    state = {
        "trace_id": "trace-log-003",
        "raw_inputs": {
            "logs": "invalid"
        },
    }

    with pytest.raises(ValueError):
        agent.run(state)


def test_log_analysis_agent_requires_llm():
    agent = LogAnalysisAgent()

    state = {
        "trace_id": "trace-log-004",
        "raw_inputs": {
            "logs": simulated_fault_logs()
        },
    }

    with pytest.raises(RuntimeError):
        agent.run(state)


def test_log_analysis_agent_rejects_invalid_llm_json():
    def invalid_llm(prompt):
        return "this is not valid JSON"

    agent = LogAnalysisAgent(llm=invalid_llm)

    state = {
        "trace_id": "trace-log-005",
        "raw_inputs": {
            "logs": simulated_fault_logs()
        },
    }

    with pytest.raises(json.JSONDecodeError):
        agent.run(state)