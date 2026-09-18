from app.agents.reasoning_agent import ReasoningAgent


class FakeLLM:

    def invoke(self, prompt):
        return """
        {
            "root_cause": "Database connection failure",
            "explanation": "The database failure occurred before downstream service errors.",
            "confidence": 0.91,
            "ranked_root_causes": [
                {
                    "rank": 1,
                    "cause": "Database connection failure",
                    "justification": "The current incident contains a database connection refused error, and downstream request failures occurred afterward.",
                    "confidence": 0.91,
                    "supporting_evidence": [
                        {
                            "source_type": "log",
                            "source_id": "log-1",
                            "service": "order-service",
                            "description": "Database connection refused",
                            "relevance": 0.95
                        }
                    ]
                },
                {
                    "rank": 2,
                    "cause": "Downstream service failure",
                    "justification": "The trace shows a downstream request failure, but it provides weaker evidence than the database error.",
                    "confidence": 0.55,
                    "supporting_evidence": []
                }
            ],
            "supporting_evidence": [
                {
                    "source_type": "log",
                    "source_id": "log-1",
                    "service": "order-service",
                    "description": "Database connection refused",
                    "relevance": 0.95
                }
            ],
            "alternative_hypotheses": [],
            "recommended_actions": [
                "Check database availability",
                "Inspect database connection configuration"
            ],
            "requires_human_review": false
        }
        """


def test_reasoning_agent():
    agent = ReasoningAgent(llm=FakeLLM())

    result = agent.run({
        "raw_inputs": {
            "logs": [
                {
                    "service": "order-service",
                    "message": "database connection refused"
                }
            ]
        },
        "agent_outputs": {
            "log_analysis_agent": {
                "summary": "Database connection failure detected"
            },
            "metrics_analysis_agent": {
                "summary": "No major metric anomaly"
            },
            "trace_analysis_agent": {
                "summary": "Request failed downstream"
            },
            "knowledge_retrieval_agent": {
                "summary": "Similar historical incidents found"
            }
        }
    })

    assert result.agent == "reasoning_agent"
    assert result.status == "completed"
    assert result.confidence == 0.91
    assert result.findings[0] == "Database connection failure"
    assert len(result.evidence) == 1


def test_reasoning_agent_handles_invalid_llm_response():

    class BadLLM:

        def invoke(self, prompt):
            return "invalid response"

    agent = ReasoningAgent(llm=BadLLM())

    result = agent.run({
        "raw_inputs": {},
        "agent_outputs": {}
    })

    assert result.agent == "reasoning_agent"
    assert result.status == "completed"
    assert result.confidence == 0.0


def test_reasoning_agent_builds_ranked_root_causes():

    agent = ReasoningAgent(llm=FakeLLM())

    result = agent.run({
        "raw_inputs": {
            "logs": [
                {
                    "service": "order-service",
                    "message": "database connection refused"
                }
            ]
        },
        "agent_outputs": {
            "log_analysis_agent": {
                "summary": "Database connection failure detected"
            }
        }
    })

    ranked = result.metadata["final_report"]["ranked_root_causes"]

    assert len(ranked) == 2

    assert ranked[0]["rank"] == 1
    assert ranked[0]["cause"] == "Database connection failure"
    assert ranked[0]["justification"]
    assert ranked[0]["confidence"] == 0.91
    assert len(ranked[0]["supporting_evidence"]) == 1

    assert ranked[1]["rank"] == 2
    assert ranked[1]["cause"] == "Downstream service failure"