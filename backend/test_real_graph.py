from app.graph import graph


def test_real_graph_e2e():
    state = {
        "raw_inputs": {
            "incident_start": "2026-09-15T10:00:00",
            "incident_end": "2026-09-15T10:10:00",
            "logs": [
                {
                    "timestamp": "2026-09-15T10:05:00",
                    "service": "order-service",
                    "level": "ERROR",
                    "message": "Request latency exceeded threshold"
                }
            ],
            "metric_anomalies": [
                {
                    "metric": "cpu_usage",
                    "value": 96.0,
                    "timestamp": "2026-09-15T10:05:00",
                    "service": "order-service",
                    "z_score": 3.2,
                    "anomaly": True
                },
                {
                    "metric": "latency_ms",
                    "value": 1250.0,
                    "timestamp": "2026-09-15T10:05:00",
                    "service": "order-service",
                    "z_score": 4.1,
                    "anomaly": True
                }
            ],
            "trace": {
                "data": [
                    {
                        "traceID": "real-graph-trace-001",
                        "spans": [
                            {
                                "traceID": "real-graph-trace-001",
                                "spanID": "root",
                                "operationName": "GET /orders",
                                "startTime": 1000000,
                                "duration": 100000,
                                "tags": [
                                    {
                                        "key": "http.status_code",
                                        "value": "500"
                                    }
                                ],
                                "process": {
                                    "serviceName": "order-service"
                                }
                            }
                        ]
                    }
                ]
            }
        }
    }

    result = graph.invoke(state)

    # Graph-level assertions
    assert "agent_outputs" in result

    agent_outputs = result["agent_outputs"]

    # Verify every implemented agent executed
    expected_agents = [
        "log_analysis_agent",
        "metrics_analysis_agent",
        "source_code_analysis_agent",
        "trace_analysis_agent",
        "knowledge_retrieval_agent",
        "reasoning_agent",
        "validation_agent",
    ]

    for agent in expected_agents:
        assert agent in agent_outputs, f"{agent} did not execute"

    # Verify Reasoning Agent produced a structured result
    reasoning = agent_outputs["reasoning_agent"]

    assert reasoning["status"] == "completed"
    assert reasoning["confidence"] >= 0.0
    assert reasoning["confidence"] <= 1.0

    # Verify a root cause was produced
    # Verify ranked root-cause analysis was produced
    final_report = reasoning["metadata"]["final_report"]

    assert "ranked_root_causes" in final_report

    ranked_root_causes = final_report["ranked_root_causes"]

    assert isinstance(ranked_root_causes, list)

    if ranked_root_causes:
    # Candidates must be ordered by rank.
        ranks = [
            candidate["rank"]
            for candidate in ranked_root_causes
        ]

        assert ranks == sorted(ranks)

        for candidate in ranked_root_causes:
            assert candidate["rank"] >= 1
            assert candidate["cause"]
            assert candidate["justification"]
            assert 0.0 <= candidate["confidence"] <= 1.0
            assert isinstance(
                candidate["supporting_evidence"],
                list,
            )

# If there is no validated root cause, human review must be required.
    if final_report["root_cause"] is None:
        assert final_report["requires_human_review"] is True

    validation = agent_outputs["validation_agent"]

    assert validation["status"] == "completed"
    assert "validated" in validation["metadata"]
    assert "requires_human_review" in validation["metadata"]

    print("\n--- AGENTS EXECUTED ---")
    print(list(agent_outputs.keys()))

    print("\n--- REASONING RESULT ---")
    print(reasoning)
    print("\n--- VALIDATION RESULT ---")
    print(agent_outputs["validation_agent"])