import unittest

from app.agents.state import (
    AgentOutput,
    AgentState,
    EvidenceItem,
    FinalReport,
)


class TestAgentState(unittest.TestCase):

    def test_create_and_mutate_state(self):
        state = AgentState(
            incident_id="INC-001",
            trace_id="trace-123",
            raw_inputs={
                "service": "order-service",
                "alert": "HighLatency",
            },
        )

        self.assertEqual(state.incident_id, "INC-001")
        self.assertEqual(state.trace_id, "trace-123")

        self.assertEqual(
            state.get_input("service"),
            "order-service",
        )

        state.set_input("severity", "critical")

        self.assertEqual(
            state.get_input("severity"),
            "critical",
        )

    def test_agent_output_write_and_read(self):
        state = AgentState(
            incident_id="INC-002",
            trace_id="trace-456",
        )

        evidence = EvidenceItem(
            source_type="log",
            source_id="log-001",
            service="order-service",
            description="Database timeout detected",
            relevance=0.95,
            agent="log_agent",
        )

        output = AgentOutput(
            agent="log_agent",
            summary="Database timeout found",
            findings=[
                "Database connection timed out"
            ],
            evidence=[evidence],
            confidence=0.9,
        )

        state.set_agent_output(
            "log_agent",
            output,
        )

        result = state.get_agent_output("log_agent")

        self.assertIsNotNone(result)
        self.assertEqual(
            result.agent,
            "log_agent",
        )
        self.assertEqual(
            result.confidence,
            0.9,
        )

    def test_agent_cannot_overwrite_output(self):
        state = AgentState(
            trace_id="trace-789",
        )

        first_output = AgentOutput(
            agent="log_agent",
            summary="First result",
        )

        second_output = AgentOutput(
            agent="log_agent",
            summary="Second result",
        )

        state.set_agent_output(
            "log_agent",
            first_output,
        )

        with self.assertRaises(ValueError):
            state.set_agent_output(
                "log_agent",
                second_output,
            )

    def test_agent_output_owner_validation(self):
        state = AgentState(
            trace_id="trace-owner",
        )

        output = AgentOutput(
            agent="metric_agent",
            summary="Metric result",
        )

        with self.assertRaises(ValueError):
            state.set_agent_output(
                "log_agent",
                output,
            )

    def test_confidence_validation(self):
        state = AgentState(
            trace_id="trace-confidence",
        )

        state.set_confidence(0.85)

        self.assertEqual(
            state.confidence,
            0.85,
        )

        with self.assertRaises(ValueError):
            state.set_confidence(1.5)

    def test_final_report(self):
        state = AgentState(
            incident_id="INC-003",
            trace_id="trace-final",
        )

        report = FinalReport(
            root_cause="Database connection pool exhaustion",
            explanation="The database pool was exhausted.",
            confidence=0.92,
            contributing_agents=[
                "log_agent",
                "metric_agent",
            ],
            recommended_actions=[
                "Increase database connection pool",
            ],
        )

        state.set_final_report(report)

        self.assertIsNotNone(state.final_report)

        self.assertEqual(
            state.final_report.root_cause,
            "Database connection pool exhaustion",
        )


if __name__ == "__main__":
    unittest.main()