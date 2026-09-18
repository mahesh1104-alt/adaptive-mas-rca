from __future__ import annotations

from typing import Any

from app.agents.state import FinalReport, EvidenceItem


class ExplainabilityFormatter:
    """
    Converts the final RCA report into a structured,
    explainable representation.

    Every evidence item retains its source metadata so that
    RCA claims can be traced back to concrete incident evidence.
    """

    SOURCE_GROUPS = {
        "log": "logs",
        "logs": "logs",
        "metric": "metrics",
        "metrics": "metrics",
        "trace": "traces",
        "traces": "traces",
        "source": "source_code",
        "source_code": "source_code",
        "code": "source_code",
        "code_diff": "source_code",
    }

    @classmethod
    def format(cls, report: FinalReport) -> dict[str, Any]:
        """
        Convert a FinalReport into a structured explainability report.
        """

        if not isinstance(report, FinalReport):
            raise TypeError("report must be a FinalReport")

        evidence = cls._format_evidence(report.supporting_evidence)

        ranked_root_causes = []

        for candidate in report.ranked_root_causes:
            ranked_root_causes.append(
                {
                    "rank": candidate.rank,
                    "cause": candidate.cause,
                    "justification": candidate.justification,
                    "confidence": candidate.confidence,
                    "supporting_evidence": [
                        cls._format_evidence_item(item)
                        for item in candidate.supporting_evidence
                    ],
                }
            )

        alternatives = []

        for hypothesis in report.alternative_hypotheses:
            alternatives.append(
                {
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "statement": hypothesis.statement,
                    "category": hypothesis.category,
                    "confidence": hypothesis.confidence,
                    "contributing_agents": list(
                        hypothesis.contributing_agents
                    ),
                    "supporting_evidence": [
                        cls._format_evidence_item(item)
                        for item in hypothesis.supporting_evidence
                    ],
                }
            )

        return {
            "root_cause": {
                "cause": report.root_cause,
                "explanation": report.explanation,
                "confidence": report.confidence,
            },
            "evidence": evidence,
            "contributing_agents": list(
                report.contributing_agents
            ),
            "ranked_root_causes": ranked_root_causes,
            "alternative_hypotheses": alternatives,
            "recommended_actions": list(
                report.recommended_actions
            ),
            "validation": {
                "requires_human_review": report.requires_human_review,
            },
        }

    @classmethod
    def _format_evidence(
        cls,
        evidence_items: list[EvidenceItem],
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Group evidence by source type.
        """

        grouped = {
            "logs": [],
            "metrics": [],
            "traces": [],
            "source_code": [],
            "other": [],
        }

        for item in evidence_items:
            formatted = cls._format_evidence_item(item)

            source_group = cls.SOURCE_GROUPS.get(
                item.source_type.lower(),
                "other",
            )

            grouped[source_group].append(formatted)

        return grouped

    @staticmethod
    def _format_evidence_item(
        item: EvidenceItem,
    ) -> dict[str, Any]:
        """
        Preserve the complete evidence provenance.
        """

        return {
            "source_type": item.source_type,
            "source_id": item.source_id,
            "timestamp": item.timestamp,
            "service": item.service,
            "field": item.field,
            "value": item.value,
            "description": item.description,
            "relevance": item.relevance,
            "agent": item.agent,
        }


def format_explainable_report(
    report: FinalReport,
) -> dict[str, Any]:
    """
    Convenience function for formatting a FinalReport.
    """

    return ExplainabilityFormatter.format(report)


__all__ = [
    "ExplainabilityFormatter",
    "format_explainable_report",
]
