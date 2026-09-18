from __future__ import annotations

from typing import Any

from app.agents.state import AgentOutput, EvidenceItem
from app.hybrid_retrieval import retrieval


class KnowledgeRetrievalAgent:
    """
    Knowledge Retrieval Agent.

    Retrieves historically relevant incidents using the existing
    hybrid ChromaDB + Neo4j retrieval pipeline.
    """

    name = "knowledge_retrieval_agent"

    def __init__(self, top_k: int = 5):
        if top_k < 1:
            raise ValueError("top_k must be at least 1")

        self.top_k = top_k

    def run(self, state: dict[str, Any]) -> AgentOutput:
        raw_inputs = state.get("raw_inputs", {})

        query = self._build_query(raw_inputs)

        if not query.strip():
            return AgentOutput(
                agent=self.name,
                status="completed",
                summary="No sufficient incident evidence was available for knowledge retrieval.",
                confidence=0.0,
            )

        results = retrieval(
            query=query,
            top_k=self.top_k,
        )

        evidence = []

        for item in results:
            incident_id = str(
                item.get("incident_id", "UNKNOWN")
            )

            relevance = float(
                item.get("relevance_score", 0.0)
            )

            description = (
                f"Historical incident {incident_id}; "
                f"service={item.get('service', '')}; "
                f"title={item.get('title', '')}; "
                f"root_cause="
                f"{item.get('document', '')}"
            )

            evidence.append(
                EvidenceItem(
                    source_type="historical_incident",
                    source_id=incident_id,
                    service=item.get("service"),
                    field="historical_incident",
                    value=item,
                    description=description,
                    relevance=max(
                        0.0,
                        min(1.0, relevance),
                    ),
                    agent=self.name,
                )
            )

        confidence = (
            max(
                (
                    evidence_item.relevance
                    for evidence_item in evidence
                ),
                default=0.0,
            )
        )

        return AgentOutput(
            agent=self.name,
            status="completed",
            summary=(
                f"Retrieved {len(results)} historically "
                "relevant incidents using hybrid retrieval."
            ),
            findings=[
                (
                    f"{item.get('incident_id', 'UNKNOWN')}: "
                    f"relevance={item.get('relevance_score', 0.0):.4f}"
                )
                for item in results
            ],
            evidence=evidence,
            confidence=confidence,
            metadata={
                "top_k": self.top_k,
                "query": query,
                "result_count": len(results),
            },
        )

    def _build_query(
        self,
        raw_inputs: dict[str, Any],
    ) -> str:
        parts = []

        logs = raw_inputs.get("logs", [])

        for log in logs:
            if isinstance(log, dict):
                service = log.get("service", "")
                message = (
                    log.get("message")
                    or log.get("template")
                    or ""
                )

                parts.append(
                    f"{service} {message}".strip()
                )
            else:
                parts.append(str(log))

        metrics = raw_inputs.get(
            "metric_anomalies",
            [],
        )

        for metric in metrics:
            if isinstance(metric, dict):
                parts.append(
                    f"{metric.get('service', '')} "
                    f"{metric.get('metric', '')} "
                    f"value={metric.get('value', '')} "
                    f"z_score={metric.get('z_score', '')}"
                )
            else:
                parts.append(str(metric))

        source_snippets = raw_inputs.get(
            "source_snippets",
            [],
        )

        for source in source_snippets:
            parts.append(str(source))

        return " ".join(
            part for part in parts if part
        ).strip()


__all__ = [
    "KnowledgeRetrievalAgent",
]