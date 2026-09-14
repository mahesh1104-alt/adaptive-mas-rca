from unittest.mock import MagicMock, patch

import pytest

from app.hybrid_retrieval import (
    _merge_results,
    _normalize_vector_distance,
    retrieval,
)


def test_normalize_vector_distance():
    assert _normalize_vector_distance(0.0) == 1.0
    assert 0.0 < _normalize_vector_distance(1.0) < 1.0


def test_merge_vector_and_graph_results():
    vector_results = [
        {
            "incident_id": "INC-005",
            "service": "order-service",
            "title": "DatabaseConnectionFailure",
            "document": "Database connection pool exhausted",
            "distance": 0.5,
            "vector_score": 0.8,
        },
        {
            "incident_id": "INC-003",
            "service": "payment-service",
            "title": "PaymentFailure",
            "document": "Payment provider timeout",
            "distance": 1.0,
            "vector_score": 0.5,
        },
    ]

    graph_results = [
        {
            "service": "order-service",
            "incident_id": "INC-005",
            "incident_title": "DatabaseConnectionFailure",
            "root_cause_id": "root-cause:pool",
            "root_cause": "Database connection pool was exhausted.",
            "hop_count": 2,
        }
    ]

    results = _merge_results(
        vector_results=vector_results,
        graph_results=graph_results,
    )

    assert len(results) == 2
    assert results[0]["incident_id"] == "INC-005"
    assert results[0]["graph_score"] == 1.0
    assert results[0]["relevance_score"] > results[1]["relevance_score"]
    assert len(results[0]["graph_evidence"]) == 1


def test_merge_adds_graph_only_incident():
    vector_results = [
        {
            "incident_id": "INC-005",
            "service": "order-service",
            "title": "DatabaseConnectionFailure",
            "document": "Database connection pool exhausted",
            "distance": 0.5,
            "vector_score": 0.8,
        }
    ]

    graph_results = [
        {
            "service": "order-service",
            "incident_id": "INC-002",
            "incident_title": "HighLatency",
            "root_cause_id": "root-cause:slow-db",
            "root_cause": "Slow database queries.",
            "hop_count": 2,
        }
    ]

    results = _merge_results(
        vector_results=vector_results,
        graph_results=graph_results,
    )

    ids = {result["incident_id"] for result in results}

    assert ids == {"INC-005", "INC-002"}
    assert results[1]["graph_score"] == 1.0


@patch("app.hybrid_retrieval.GraphDatabase.driver")
@patch("app.hybrid_retrieval.search_similar_incidents")
@patch("app.hybrid_retrieval.generate_incident_embedding")
def test_retrieval_returns_hybrid_results(
    mock_embedding,
    mock_search,
    mock_driver,
):
    mock_embedding.return_value = [0.1] * 384

    mock_search.return_value = {
        "ids": [["INC-005", "INC-002", "INC-003"]],
        "distances": [[0.4, 0.8, 1.2]],
        "documents": [
            [
                "Database connection pool exhausted",
                "Slow database queries",
                "Payment provider timeout",
            ]
        ],
        "metadatas": [
            [
                {"service": "order-service", "alert_name": "DatabaseFailure"},
                {"service": "order-service", "alert_name": "HighLatency"},
                {"service": "payment-service", "alert_name": "PaymentFailure"},
            ]
        ],
    }

    driver = MagicMock()
    session = MagicMock()

    graph_records = [
        {
            "service": "order-service",
            "incident_id": "INC-005",
            "incident_title": "DatabaseFailure",
            "root_cause_id": "root-cause:pool",
            "root_cause": "Database connection pool was exhausted.",
            "hop_count": 2,
        },
        {
            "service": "order-service",
            "incident_id": "INC-002",
            "incident_title": "HighLatency",
            "root_cause_id": "root-cause:slow-db",
            "root_cause": "Slow database queries.",
            "hop_count": 2,
        },
    ]

    session.run.return_value = [
        MagicMock(data=lambda record=record: record)
        for record in graph_records
    ]

    driver.session.return_value.__enter__.return_value = session
    mock_driver.return_value = driver

    results = retrieval(
        "Database connection timeout",
        top_k=3,
    )

    assert len(results) == 3
    assert results[0]["incident_id"] == "INC-005"
    assert results[0]["graph_score"] == 1.0
    assert results[0]["relevance_score"] > 0
    assert results[0]["graph_evidence"]


def test_retrieval_rejects_empty_query():
    with pytest.raises(ValueError, match="query cannot be empty"):
        retrieval("")


def test_retrieval_rejects_invalid_top_k():
    with pytest.raises(ValueError, match="top_k must be at least 1"):
        retrieval("database failure", top_k=0)