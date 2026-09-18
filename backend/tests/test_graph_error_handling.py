import pytest

from app.graph import build_graph


class FailingLLM:
    def invoke(self, *args, **kwargs):
        raise RuntimeError("Intentional Log Agent failure for testing")


def test_graph_continues_when_log_agent_fails():
    graph = build_graph(log_llm=FailingLLM())

    state = {
        "raw_inputs": {
            "logs": [
                {
                    "timestamp": "2026-09-16T10:00:00",
                    "service": "payment-service",
                    "level": "ERROR",
                    "message": "Database connection failed",
                }
            ],
            "metrics": [],
            "trace": {
                "trace_id": "test-trace",
                "spans": [],
            },
            "source_code": [],
        },
        "agent_outputs": {},
    }

    result = graph.invoke(state)

    assert "agent_outputs" in result

    outputs = result["agent_outputs"]

    # Log Agent should have failed gracefully.
    assert "log_analysis_agent" in outputs
    assert outputs["log_analysis_agent"]["status"] == "failed"

    # The graph should still execute downstream agents.
    assert "knowledge_retrieval_agent" in outputs
    assert "reasoning_agent" in outputs
    assert "validation_agent" in outputs

    # Human review should be required because an agent failed.
    assert outputs["log_analysis_agent"]["metadata"]["requires_human_review"] is True