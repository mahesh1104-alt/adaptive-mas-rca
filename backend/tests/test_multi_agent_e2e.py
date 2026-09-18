import time

from app.graph import build_graph


TEST_INCIDENTS = [
    {
        "name": "database_connection_failure",
        "requires_root_cause": True,
        "raw_inputs": {
            "logs": [
                {
                    "timestamp": "2026-09-16T10:00:00",
                    "service": "payment-service",
                    "level": "ERROR",
                    "message": "Database connection failed",
                },
                {
                    "timestamp": "2026-09-16T10:00:05",
                    "service": "payment-service",
                    "level": "ERROR",
                    "message": "Connection pool exhausted",
                },
            ],
            "metric_anomalies": [
                {
                    "timestamp": "2026-09-16T10:00:00",
                    "service": "payment-service",
                    "metric": "db_connection_pool_usage",
                    "value": 98,
                }
            ],
            "trace": {
                "trace_id": "trace-db-001",
                "spans": [
                    {
                        "span_id": "span-db-001",
                        "service": "payment-service",
                        "operation": "process_payment",
                        "duration_ms": 2500,
                        "status": "ERROR",
                        "tags": {
                            "error": True,
                            "http.status_code": 500,
                            "db.operation": "connect",
                        },
                    }
                ],
            },
            "source_snippets": [],
            "recent_commits": [],
        },
    },

    {
        "name": "high_cpu",
        "requires_root_cause": True,
        "raw_inputs": {
            "logs": [
                {
                    "timestamp": "2026-09-16T11:00:00",
                    "service": "order-service",
                    "level": "WARN",
                    "message": "Request processing time increased",
                }
            ],
            "metric_anomalies": [
                {
                    "timestamp": "2026-09-16T11:00:00",
                    "service": "order-service",
                    "metric": "cpu_usage",
                    "value": 97,
                },
                {
                    "timestamp": "2026-09-16T11:00:05",
                    "service": "order-service",
                    "metric": "request_latency_ms",
                    "value": 2400,
                },
            ],
            "trace": {
                "trace_id": "trace-cpu-001",
                "spans": [
                    {
                        "span_id": "span-cpu-001",
                        "service": "order-service",
                        "operation": "process_order",
                        "duration_ms": 2400,
                        "status": "ERROR",
                        "tags": {
                            "error": True,
                            "http.status_code": 500,
                        },
                    }
                ],
            },
            "source_snippets": [
                {
                    "file": "order_service.py",
                    "function": "process_order",
                    "line_start": 142,
                    "line_end": 142,
                    "code": (
                        "while pending_orders: "
                        "process_order(pending_orders.pop())"
                    ),
                    "issue": (
                        "Unbounded CPU-intensive loop processes "
                        "a large pending order queue."
                    ),
                }
            ],
            "recent_commits": [
                {
                    "commit_sha": "test-commit-cpu-001",
                    "message": "Added order processing logic",
                }
            ],
        },
    },

    {
        "name": "payment_timeout",
        "requires_root_cause": False,
        "raw_inputs": {
            "logs": [
                {
                    "timestamp": "2026-09-16T12:00:00",
                    "service": "payment-service",
                    "level": "ERROR",
                    "message": "Payment provider request timed out",
                }
            ],
            "metric_anomalies": [
                {
                    "timestamp": "2026-09-16T12:00:00",
                    "service": "payment-service",
                    "metric": "request_latency_ms",
                    "value": 5000,
                }
            ],
            "trace": {
                "trace_id": "trace-payment-001",
                "spans": [
                    {
                        "span_id": "span-payment-001",
                        "service": "payment-service",
                        "operation": "payment_provider_request",
                        "duration_ms": 5000,
                        "status": "ERROR",
                        "tags": {
                            "error": True,
                            "http.status_code": 504,
                        },
                    }
                ],
            },
            "source_snippets": [],
            "recent_commits": [],
        },
    },

    {
        "name": "service_error",
        "requires_root_cause": True,
        "raw_inputs": {
            "logs": [
                {
                    "timestamp": "2026-09-16T13:00:00",
                    "service": "order-service",
                    "level": "ERROR",
                    "message": "Unhandled exception while processing order",
                }
            ],
            "metric_anomalies": [
                {
                    "timestamp": "2026-09-16T13:00:00",
                    "service": "order-service",
                    "metric": "error_rate",
                    "value": 18,
                }
            ],
            "trace": {
                "trace_id": "trace-error-001",
                "spans": [
                    {
                        "span_id": "span-error-001",
                        "service": "order-service",
                        "operation": "process_order",
                        "duration_ms": 1800,
                        "status": "ERROR",
                        "tags": {
                            "error": True,
                            "http.status_code": 500,
                        },
                    }
                ],
            },
            "source_snippets": [
                {
                    "file": "order_service.py",
                    "function": "process_order",
                    "line_start": 120,
                    "line_end": 150,
                    "code": (
                        "def process_order(order):\n"
                        "    result = process_payment(order)\n"
                        "    return result"
                    ),
                    "change": "Added order processing logic.",
                }
            ],
            "recent_commits": [
                {
                    "commit_sha": "test-commit-error-001",
                    "message": "Added order processing logic",
                }
            ],
        },
    },

    {
        "name": "memory_pressure",
        "requires_root_cause": True,
        "raw_inputs": {
            "logs": [
                {
                    "timestamp": "2026-09-16T14:00:00",
                    "service": "inventory-service",
                    "level": "ERROR",
                    "message": "Out of memory condition detected",
                }
            ],
            "metric_anomalies": [
                {
                    "timestamp": "2026-09-16T14:00:00",
                    "service": "inventory-service",
                    "metric": "memory_usage",
                    "value": 99,
                }
            ],
            "trace": {
                "trace_id": "trace-memory-001",
                "spans": [
                    {
                        "span_id": "span-memory-001",
                        "service": "inventory-service",
                        "operation": "load_inventory",
                        "duration_ms": 3200,
                        "status": "ERROR",
                        "tags": {
                            "error": True,
                            "http.status_code": 500,
                        },
                    }
                ],
            },
            "source_snippets": [],
            "recent_commits": [],
        },
    },
]


def test_multi_agent_pipeline_end_to_end():
    graph = build_graph()

    execution_times = []

    expected_agents = {
        "log_analysis_agent",
        "metrics_analysis_agent",
        "source_code_analysis_agent",
        "trace_analysis_agent",
        "knowledge_retrieval_agent",
        "reasoning_agent",
        "validation_agent",
    }

    for incident in TEST_INCIDENTS:

        start = time.perf_counter()

        result = graph.invoke(
            {
                "raw_inputs": incident["raw_inputs"],
                "agent_outputs": {},
            }
        )

        elapsed = time.perf_counter() - start
        execution_times.append(elapsed)

        print(
            f"\nIncident: {incident['name']}"
            f"\nExecution time: {elapsed:.2f} seconds"
        )

        # ---------------------------------------------------------
        # GRAPH OUTPUT
        # ---------------------------------------------------------

        assert "agent_outputs" in result

        outputs = result["agent_outputs"]

        # Every expected graph node must produce an output.
        assert expected_agents.issubset(outputs.keys())

        # ---------------------------------------------------------
        # REASONING OUTPUT
        # ---------------------------------------------------------

        reasoning_output = outputs["reasoning_agent"]

        assert "metadata" in reasoning_output
        assert "final_report" in reasoning_output["metadata"]

        final_report = reasoning_output["metadata"]["final_report"]
        print("\n===== REASONING OUTPUT =====")
        print(reasoning_output)

        print("\n===== FINAL REPORT =====")
        print(final_report)

        print("\n===== ALL AGENT OUTPUTS =====")
        for agent_name, agent_output in outputs.items():
            print(f"\n--- {agent_name} ---")
            print(agent_output)
        # ---------------------------------------------------------
        # FINAL REPORT STRUCTURE
        # ---------------------------------------------------------

        required_fields = {
            "root_cause",
            "explanation",
            "confidence",
            "supporting_evidence",
            "alternative_hypotheses",
            "contributing_agents",
            "recommended_actions",
            "ranked_root_causes",
            "requires_human_review",
        }

        assert required_fields.issubset(final_report.keys())

        # ---------------------------------------------------------
        # ROOT CAUSE VALIDATION
        # ---------------------------------------------------------

        if incident["requires_root_cause"]:

            assert final_report["root_cause"], (
                f"Expected a root cause for incident "
                f"{incident['name']}, but received: "
                f"{final_report['root_cause']}"
            )

            assert final_report["confidence"] >= 0.0
            assert len(final_report["ranked_root_causes"]) >= 1

        else:

            # For incidents where the available evidence only proves
            # a symptom/anomaly, the correct result is an
            # undetermined root cause requiring human review.

            assert final_report["root_cause"] in (None, "")

            assert final_report["requires_human_review"] is True

            assert final_report["confidence"] == 0.0

        # ---------------------------------------------------------
        # AGENT OUTPUT VALIDATION
        # ---------------------------------------------------------

        for agent_name in expected_agents:

            agent_output = outputs[agent_name]

            # Every graph node must return an output dictionary.
            assert agent_output is not None
            assert isinstance(agent_output, dict)

            # Every implemented agent must expose a confidence score.
            assert "confidence" in agent_output

            confidence = agent_output["confidence"]

            assert isinstance(confidence, (int, float))
            assert 0.0 <= confidence <= 1.0

    # -------------------------------------------------------------
    # PERFORMANCE SUMMARY
    # -------------------------------------------------------------

    average_time = sum(execution_times) / len(execution_times)

    print(
        f"\nAverage execution time for "
        f"{len(TEST_INCIDENTS)} incidents: "
        f"{average_time:.2f} seconds"
    )

    assert len(execution_times) == len(TEST_INCIDENTS)