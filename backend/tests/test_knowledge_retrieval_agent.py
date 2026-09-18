from app.agents.knowledge_retrieval_agent import (
    KnowledgeRetrievalAgent,
)


def test_build_query():
    agent = KnowledgeRetrievalAgent()

    query = agent._build_query(
        {
            "logs": [
                {
                    "service": "order-service",
                    "message": "database timeout",
                }
            ],
            "metric_anomalies": [
                {
                    "service": "order-service",
                    "metric": "cpu_usage",
                    "value": 96,
                    "z_score": 3.2,
                }
            ],
        }
    )

    assert "order-service" in query
    assert "database timeout" in query
    assert "cpu_usage" in query


def test_empty_input():
    agent = KnowledgeRetrievalAgent()

    result = agent.run(
        {
            "raw_inputs": {}
        }
    )

    assert result.agent == "knowledge_retrieval_agent"
    assert result.status == "completed"
    assert result.confidence == 0.0