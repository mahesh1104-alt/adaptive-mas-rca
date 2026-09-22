from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    source_type: str
    source_id: str | None = None
    timestamp: str | None = None
    service: str | None = None
    field: str | None = None
    value: Any = None
    description: str
    relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    agent: str


class Hypothesis(BaseModel):
    hypothesis_id: str
    statement: str
    category: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    supporting_evidence: list[EvidenceItem] = Field(default_factory=list)
    contributing_agents: list[str] = Field(default_factory=list)


class RankedRootCause(BaseModel):
    rank: int
    cause: str
    justification: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    supporting_evidence: list[EvidenceItem] = Field(default_factory=list)


class AgentOutput(BaseModel):
    agent: str
    status: str = "completed"
    summary: str = ""
    findings: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FinalReport(BaseModel):
    root_cause: str | None = None
    explanation: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    supporting_evidence: list[EvidenceItem] = Field(default_factory=list)
    alternative_hypotheses: list[Hypothesis] = Field(default_factory=list)
    contributing_agents: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    ranked_root_causes: list[RankedRootCause] = Field(default_factory=list)
    requires_human_review: bool = False


class AgentState(BaseModel):
    """
    Shared state passed between LangGraph agents.

    Agents should read from the appropriate sections and write
    only to their own output section.
    """

    incident_id: str | None = None
    trace_id: str

    raw_inputs: dict[str, Any] = Field(default_factory=dict)

    agent_outputs: dict[str, AgentOutput] = Field(default_factory=dict)

    agent_weights: dict[str, float] = Field(default_factory=dict)

    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    final_report: FinalReport | None = None

    def get_input(self, key: str, default: Any = None) -> Any:
        """Read a value from the shared raw input section."""
        return self.raw_inputs.get(key, default)

    def set_input(self, key: str, value: Any) -> None:
        """Write a value to the shared raw input section."""
        self.raw_inputs[key] = value

    def get_agent_output(self, agent: str) -> AgentOutput | None:
        """Read the output produced by a specific agent."""
        return self.agent_outputs.get(agent)

    def set_agent_output(
        self,
        agent: str,
        output: AgentOutput,
    ) -> None:
        """
        Store an agent's output.

        Each agent owns its own output key. An agent cannot write
        to another agent's section.
        """

        if output.agent != agent:
            raise ValueError(
                f"Agent output owner mismatch: "
                f"writer='{agent}', output.agent='{output.agent}'"
            )

        if agent in self.agent_outputs:
            raise ValueError(
                f"Agent '{agent}' already has an output. "
                "Overwriting agent outputs is not allowed."
            )

        self.agent_outputs[agent] = output

    def get_all_agent_outputs(self) -> dict[str, AgentOutput]:
        """Return all agent outputs."""
        return dict(self.agent_outputs)

    def set_confidence(self, confidence: float) -> None:
        """Set the shared confidence score."""
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0.")

        self.confidence = confidence

    def set_final_report(self, report: FinalReport) -> None:
        """Store the final validated RCA report."""
        self.final_report = report