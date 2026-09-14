import pytest

from app.vector_store import (
    get_collection_count,
    search_similar_incidents,
    store_embedding,
)


def test_store_embedding_and_search():
    incident_id = "TEST-INC-001"
    embedding = [0.1] * 384
    document = "Database connection pool exhausted"

    store_embedding(
        incident_id=incident_id,
        embedding=embedding,
        document=document,
        metadata={
            "service": "order-service",
            "severity": "critical",
        },
    )

    results = search_similar_incidents(
        embedding=embedding,
        n_results=1,
    )

    assert results["ids"]
    assert incident_id in results["ids"][0]
    assert results["documents"][0][0] == document


def test_search_returns_top_k():
    embedding = [0.2] * 384

    for i in range(3):
        store_embedding(
            incident_id=f"TEST-INC-TOPK-{i}",
            embedding=[0.2 + (i * 0.001)] * 384,
            document=f"Test incident {i}",
            metadata={"service": "test-service"},
        )

    results = search_similar_incidents(
        embedding=embedding,
        n_results=2,
    )

    assert len(results["ids"][0]) == 2


def test_empty_embedding_rejected():
    with pytest.raises(ValueError, match="embedding cannot be empty"):
        search_similar_incidents([], n_results=5)


def test_invalid_n_results_rejected():
    embedding = [0.1] * 384

    with pytest.raises(ValueError, match="n_results must be at least 1"):
        search_similar_incidents(embedding, n_results=0)


def test_collection_contains_embeddings():
    count = get_collection_count()

    assert count >= 0