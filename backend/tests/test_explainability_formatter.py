from app.agents.explainability_formatter import ExplainabilityFormatter
from app.agents.state import (
    EvidenceItem,
    FinalReport,
    RankedRootCause,
)


def test_incident_1_database_resource_issue():
    log_evidence = EvidenceItem(
        source_type="log",
        source_id="log-001",
        timestamp="2026-09-17T10:05:00",
        service="order-service",
        field="message",
        value="Database connection pool exhausted",
        description="Database connection pool exhausted",
        relevance=0.98,
        agent="log_analysis_agent",
    )

    metric_evidence = EvidenceItem(
        source_type="metric",
        source_id="metric-001",
        timestamp="2026-09-17T10:05:00",
        service="order-service",
        field="db_connection_usage",
        value=99.0,
        description="Database connection usage reached 99%",
        relevance=0.95,
        agent="metrics_analysis_agent",
    )

    trace_evidence = EvidenceItem(
        source_type="trace",
        source_id="trace-span-001",
        timestamp="2026-09-17T10:05:01",
        service="order-service",
        field="duration_ms",
        value=2500,
        description="Database span became the latency bottleneck",
        relevance=0.92,
        agent="trace_analysis_agent",
    )

    report = FinalReport(
        root_cause="Database connection pool exhaustion",
        explanation=(
            "The connection pool exhaustion is supported by the "
            "application log, connection-usage metric, and trace evidence."
        ),
        confidence=0.93,
        supporting_evidence=[
            log_evidence,
            metric_evidence,
            trace_evidence,
        ],
        contributing_agents=[
            "log_analysis_agent",
            "metrics_analysis_agent",
            "trace_analysis_agent",
        ],
        ranked_root_causes=[
            RankedRootCause(
                rank=1,
                cause="Database connection pool exhaustion",
                justification="Multiple independent evidence sources support the cause.",
                confidence=0.93,
                supporting_evidence=[
                    log_evidence,
                    metric_evidence,
                    trace_evidence,
                ],
            )
        ],
        recommended_actions=[
            "Increase or tune the database connection pool.",
        ],
        requires_human_review=False,
    )

    result = ExplainabilityFormatter.format(report)

    assert result["root_cause"]["cause"] == (
        "Database connection pool exhaustion"
    )
    assert result["root_cause"]["confidence"] == 0.93

    assert len(result["evidence"]["logs"]) == 1
    assert len(result["evidence"]["metrics"]) == 1
    assert len(result["evidence"]["traces"]) == 1

    assert result["evidence"]["logs"][0]["source_id"] == "log-001"
    assert result["evidence"]["metrics"][0]["source_id"] == "metric-001"
    assert result["evidence"]["traces"][0]["source_id"] == "trace-span-001"

    assert result["evidence"]["logs"][0]["agent"] == "log_analysis_agent"
    assert result["evidence"]["metrics"][0]["agent"] == "metrics_analysis_agent"
    assert result["evidence"]["traces"][0]["agent"] == "trace_analysis_agent"

    assert result["ranked_root_causes"][0]["rank"] == 1
    assert len(
        result["ranked_root_causes"][0]["supporting_evidence"]
    ) == 3

    assert result["validation"]["requires_human_review"] is False


def test_incident_2_application_code_failure():
    source_evidence = EvidenceItem(
        source_type="code_diff",
        source_id="commit-abc123",
        timestamp="2026-09-17T11:10:00",
        service="payment-service",
        field="commit",
        value="abc123",
        description="Recent code change removed payment timeout handling",
        relevance=0.97,
        agent="source_code_analysis_agent",
    )

    log_evidence = EvidenceItem(
        source_type="log",
        source_id="log-099",
        timestamp="2026-09-17T11:10:05",
        service="payment-service",
        field="level",
        value="ERROR",
        description="Payment request failed with unhandled exception",
        relevance=0.94,
        agent="log_analysis_agent",
    )

    report = FinalReport(
        root_cause="Unhandled payment exception introduced by recent code change",
        explanation=(
            "The source-code change and corresponding application error "
            "support an application-level code defect."
        ),
        confidence=0.89,
        supporting_evidence=[
            source_evidence,
            log_evidence,
        ],
        contributing_agents=[
            "source_code_analysis_agent",
            "log_analysis_agent",
        ],
        ranked_root_causes=[
            RankedRootCause(
                rank=1,
                cause="Unhandled payment exception introduced by recent code change",
                justification=(
                    "The code diff identifies the changed behavior and "
                    "the log shows the resulting application failure."
                ),
                confidence=0.89,
                supporting_evidence=[
                    source_evidence,
                    log_evidence,
                ],
            )
        ],
        recommended_actions=[
            "Restore explicit payment timeout handling.",
        ],
        requires_human_review=False,
    )

    result = ExplainabilityFormatter.format(report)

    assert result["root_cause"]["cause"] == (
        "Unhandled payment exception introduced by recent code change"
    )

    assert result["root_cause"]["confidence"] == 0.89

    assert len(result["evidence"]["source_code"]) == 1
    assert len(result["evidence"]["logs"]) == 1

    assert result["evidence"]["source_code"][0]["source_id"] == (
        "commit-abc123"
    )
    assert result["evidence"]["logs"][0]["source_id"] == "log-099"

    assert result["evidence"]["source_code"][0]["agent"] == (
        "source_code_analysis_agent"
    )
    assert result["evidence"]["logs"][0]["agent"] == (
        "log_analysis_agent"
    )

    assert result["ranked_root_causes"][0]["rank"] == 1
    assert len(
        result["ranked_root_causes"][0]["supporting_evidence"]
    ) == 2

    assert result["validation"]["requires_human_review"] is False
