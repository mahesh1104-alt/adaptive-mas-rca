from unittest.mock import patch

import pytest

from app.rag_prompt import (
    estimate_tokens,
    format_rag_prompt,
    generate_rag_response,
)


def sample_evidence():
    return [
        {
            "incident_id": "INC-005",
            "service": "order-service",
            "title": "DatabaseConnectionFailure",
            "document": (
                "Order service unable to connect to database. "
                "Database connection attempts were failing."
            ),
            "vector_score": 0.62,
            "graph_score": 1.0,
            "relevance_score": 0.73,
            "graph_evidence": [
                {
                    "service": "order-service",
                    "root_cause": (
                        "Database connection pool was exhausted."
                    ),
                    "hop_count": 2,
                }
            ],
        },
        {
            "incident_id": "INC-020",
            "service": "order-worker",
            "title": "MessageProcessingFailure",
            "document": (
                "Background workers failed to process "
                "incoming order messages."
            ),
            "vector_score": 0.50,
            "graph_score": 1.0,
            "relevance_score": 0.65,
            "graph_evidence": [
                {
                    "service": "order-worker",
                    "root_cause": (
                        "Malformed message payloads."
                    ),
                    "hop_count": 2,
                }
            ],
        },
    ]


def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcdefgh") == 2


def test_format_prompt_contains_current_logs():
    prompt = format_rag_prompt(
        query="Database connection timeout",
        logs=[
            {
                "level": "ERROR",
                "template": (
                    "Database connection attempts are timing out"
                ),
            }
        ],
    )

    assert "CURRENT LOGS" in prompt
    assert "Database connection attempts are timing out" in prompt


def test_format_prompt_contains_metrics():
    prompt = format_rag_prompt(
        query="Database connection timeout",
        metrics=[
            {
                "name": "request_latency",
                "value": 245.7,
                "unit": "ms",
                "service": "order-service",
            }
        ],
    )

    assert "CURRENT METRICS" in prompt
    assert "request_latency=245.7 ms" in prompt


def test_format_prompt_contains_citations_and_graph_facts():
    prompt = format_rag_prompt(
        query="Database connection timeout",
        retrieved_evidence=sample_evidence(),
    )

    assert "[Incident #1: INC-005]" in prompt
    assert "[Incident #2: INC-020]" in prompt
    assert "Database connection pool was exhausted." in prompt
    assert "Graph hops: 2" in prompt


def test_higher_relevance_evidence_is_kept_first():
    evidence = sample_evidence()

    prompt = format_rag_prompt(
        query="Database connection timeout",
        retrieved_evidence=evidence,
        token_budget=2500,
    )

    assert prompt.index("INC-005") < prompt.index("INC-020")


def test_lowest_relevance_evidence_is_removed_when_budget_is_small():
    evidence = sample_evidence()

    prompt = format_rag_prompt(
        query="Database connection timeout",
        retrieved_evidence=evidence,
        token_budget=300,
    )

    assert "INC-005" in prompt
    assert "INC-020" not in prompt


def test_empty_query_rejected():
    with pytest.raises(ValueError):
        format_rag_prompt(query="")


def test_invalid_query_type_rejected():
    with pytest.raises(TypeError):
        format_rag_prompt(query=None)


def test_invalid_token_budget_rejected():
    with pytest.raises(ValueError):
        format_rag_prompt(
            query="test",
            token_budget=0,
        )


def test_generate_rag_response():
    mocked_response = {
        "message": {
            "content": "The likely root cause is database connection exhaustion."
        }
    }

    with patch("app.rag_prompt.ollama.chat") as mock_chat:
        mock_chat.return_value = mocked_response

        response = generate_rag_response(
            "Analyze this incident."
        )

    assert response == (
        "The likely root cause is database connection exhaustion."
    )

    mock_chat.assert_called_once()


def test_generate_rag_response_rejects_empty_prompt():
    with pytest.raises(ValueError):
        generate_rag_response("")


def test_generate_rag_response_rejects_non_string():
    with pytest.raises(TypeError):
        generate_rag_response(None)