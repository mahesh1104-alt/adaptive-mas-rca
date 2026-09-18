from app.trace_analysis_agent import (
    TraceAnalysisAgent,
    analyze_trace,
)
from app.trace_preprocessing import (
    create_faulty_request_trace,
    preprocess_trace,
)


def test_faulty_trace_identifies_inventory_service():
    trace = create_faulty_request_trace()

    summary = preprocess_trace(trace)

    result = analyze_trace(summary)

    assert result["service"] == "inventory-service"
    assert result["span"] == "check-inventory"
    assert result["issue_type"] == "failure"


def test_faulty_trace_has_high_confidence():
    trace = create_faulty_request_trace()

    summary = preprocess_trace(trace)

    result = analyze_trace(summary)

    assert 0.0 <= result["confidence"] <= 1.0
    assert result["confidence"] >= 0.9


def test_faulty_trace_contains_evidence():
    trace = create_faulty_request_trace()

    summary = preprocess_trace(trace)

    result = analyze_trace(summary)

    assert len(result["evidence"]) > 0


def test_agent_returns_structured_output():
    trace = create_faulty_request_trace()

    summary = preprocess_trace(trace)

    agent = TraceAnalysisAgent()

    result = agent.analyze(summary)

    assert result.service == "inventory-service"
    assert result.span == "check-inventory"
    assert result.issue_type == "failure"
    assert isinstance(result.confidence, float)
    assert isinstance(result.evidence, list)


def test_empty_trace_is_rejected():
    agent = TraceAnalysisAgent()

    try:
        agent.analyze({})
        assert False, "Expected ValueError"
    except ValueError:
        assert True


def test_latency_trace():
    trace = {
        "data": [
            {
                "traceID": "latency-trace-001",
                "spans": [
                    {
                        "traceID": "latency-trace-001",
                        "spanID": "root",
                        "operationName": "GET /orders",
                        "startTime": 1000000,
                        "duration": 100000,
                        "references": [],
                        "process": {
                            "serviceName": "api-gateway"
                        },
                        "tags": [],
                    },
                    {
                        "traceID": "latency-trace-001",
                        "spanID": "slow",
                        "operationName": "GET /inventory",
                        "startTime": 1010000,
                        "duration": 900000,
                        "references": [
                            {
                                "refType": "CHILD_OF",
                                "traceID": "latency-trace-001",
                                "spanID": "root",
                            }
                        ],
                        "process": {
                            "serviceName": "inventory-service"
                        },
                        "tags": [],
                    },
                ],
            }
        ]
    }

    summary = preprocess_trace(trace)

    result = analyze_trace(summary)

    assert result["service"] == "inventory-service"
    assert result["span"] == "GET /inventory"
    assert result["issue_type"] == "latency"