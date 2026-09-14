from unittest.mock import patch

import pytest
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda

from app.langchain_retriever import HybridLangChainRetriever


def sample_results():
    return [
        {
            "incident_id": "INC-005",
            "service": "order-service",
            "title": "DatabaseConnectionFailure",
            "document": "Database connection pool was exhausted.",
            "vector_distance": 0.2,
            "vector_score": 0.8333,
            "graph_score": 1.0,
            "relevance_score": 0.8833,
            "graph_evidence": [
                {
                    "service": "order-service",
                    "root_cause": "Database connection pool was exhausted.",
                    "hop_count": 2,
                }
            ],
        },
        {
            "incident_id": "INC-002",
            "service": "order-service",
            "title": "HighLatency",
            "document": "Slow database queries.",
            "vector_distance": 0.5,
            "vector_score": 0.6667,
            "graph_score": 1.0,
            "relevance_score": 0.7667,
            "graph_evidence": [
                {
                    "service": "order-service",
                    "root_cause": "Slow database queries.",
                    "hop_count": 2,
                }
            ],
        },
    ]


def test_retriever_direct_invoke():
    with patch(
        "app.langchain_retriever.retrieval",
        return_value=sample_results(),
    ):
        retriever = HybridLangChainRetriever(
            top_k=3,
            score_threshold=0.5,
        )

        documents = retriever.invoke(
            "Database connection timeout"
        )

    assert len(documents) == 2
    assert all(isinstance(doc, Document) for doc in documents)

    assert documents[0].metadata["incident_id"] == "INC-005"
    assert documents[0].metadata["service"] == "order-service"
    assert documents[0].metadata["relevance_score"] == 0.8833

    assert "Database connection pool was exhausted." in (
        documents[0].page_content
    )

    assert "Graph evidence:" in documents[0].page_content


def test_score_threshold_filters_results():
    results = sample_results()

    results[1]["relevance_score"] = 0.4

    with patch(
        "app.langchain_retriever.retrieval",
        return_value=results,
    ):
        retriever = HybridLangChainRetriever(
            top_k=3,
            score_threshold=0.5,
        )

        documents = retriever.invoke(
            "Database connection timeout"
        )

    assert len(documents) == 1
    assert documents[0].metadata["incident_id"] == "INC-005"


def test_top_k_is_passed_to_hybrid_retrieval():
    with patch(
        "app.langchain_retriever.retrieval",
        return_value=sample_results(),
    ) as mock_retrieval:
        retriever = HybridLangChainRetriever(
            top_k=7,
            score_threshold=0.0,
        )

        retriever.invoke("Database connection timeout")

    mock_retrieval.assert_called_once_with(
        query="Database connection timeout",
        top_k=7,
    )


def test_invalid_top_k():
    with pytest.raises(ValueError):
        HybridLangChainRetriever(top_k=0)


def test_invalid_score_threshold():
    with pytest.raises(ValueError):
        HybridLangChainRetriever(
            score_threshold=1.5,
        )


def test_langchain_chain_integration():
    with patch(
        "app.langchain_retriever.retrieval",
        return_value=sample_results(),
    ):
        retriever = HybridLangChainRetriever(
            top_k=2,
            score_threshold=0.5,
        )

        def format_documents(query):
            documents = retriever.invoke(query)

            return "\n".join(
                document.page_content
                for document in documents
            )

        chain = (
            RunnableLambda(format_documents)
            | RunnableLambda(
                lambda context: (
                    f"Retrieved context:\n{context}"
                )
            )
        )

        result = chain.invoke(
            "Database connection timeout"
        )

    assert "Retrieved context:" in result
    assert "Database connection pool was exhausted." in result


def test_langgraph_node_integration():
    from langgraph.graph import END, START, StateGraph
    from typing_extensions import TypedDict

    class State(TypedDict):
        query: str
        documents: list

    with patch(
        "app.langchain_retriever.retrieval",
        return_value=sample_results(),
    ):
        retriever = HybridLangChainRetriever(
            top_k=2,
            score_threshold=0.5,
        )

        def retrieve_node(state):
            documents = retriever.invoke(state["query"])

            return {
                "documents": documents,
            }

        graph_builder = StateGraph(State)

        graph_builder.add_node(
            "retrieve",
            retrieve_node,
        )

        graph_builder.add_edge(
            START,
            "retrieve",
        )

        graph_builder.add_edge(
            "retrieve",
            END,
        )

        graph = graph_builder.compile()

        result = graph.invoke(
            {
                "query": "Database connection timeout",
                "documents": [],
            }
        )

    assert len(result["documents"]) == 2
    assert isinstance(result["documents"][0], Document)