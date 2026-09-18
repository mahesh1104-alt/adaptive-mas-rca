from __future__ import annotations

from typing import Any

from app.agents.state import AgentOutput


class ValidationAgent:
    name = "validation_agent"

    def __init__(
        self,
        confidence_threshold: float = 0.70,
    ):
        self.confidence_threshold = confidence_threshold

    def run(self, state: dict[str, Any]) -> AgentOutput:
        agent_outputs = state.get("agent_outputs", {})
        raw_inputs = state.get("raw_inputs", {})

        reasoning = agent_outputs.get("reasoning_agent", {})

        issues = []
        checks = []

        # ---------------------------------------------------------
        # 1. Check that Reasoning Agent produced a result
        # ---------------------------------------------------------
        if not reasoning:
            issues.append("Reasoning Agent output is missing.")
        else:
            checks.append("Reasoning Agent output is present.")

        # ---------------------------------------------------------
        # 2. Extract final report
        # ---------------------------------------------------------
        if isinstance(reasoning, dict):
            report = reasoning.get("metadata", {}).get(
                "final_report",
                {}
            )
        else:
            report = {}

        root_cause = report.get("root_cause")

        try:
            confidence = float(
                report.get(
                    "confidence",
                    reasoning.get("confidence", 0.0)
                    if isinstance(reasoning, dict)
                    else 0.0,
                )
            )
        except (TypeError, ValueError):
            confidence = 0.0
            issues.append("Reasoning confidence is invalid.")

        confidence = max(0.0, min(1.0, confidence))

        # ---------------------------------------------------------
        # 3. Validate root cause exists
        # ---------------------------------------------------------
        root_cause_present = bool(
            root_cause and str(root_cause).strip()
        )

        if not root_cause_present:
            issues.append("No root cause was produced.")
        else:
            checks.append("Root cause is present.")

        # ---------------------------------------------------------
        # 4. Validate supporting evidence
        # ---------------------------------------------------------
        evidence = report.get("supporting_evidence", [])

        if not isinstance(evidence, list):
            evidence = []

        evidence_count = len(evidence)

        if evidence_count == 0:
            issues.append(
                "No supporting evidence was provided for the root cause."
            )
        else:
            checks.append(
                f"{evidence_count} supporting evidence item(s) provided."
            )

        # ---------------------------------------------------------
        # 5. Check evidence against current incident inputs
        # ---------------------------------------------------------
        current_evidence_text = str(raw_inputs).lower()

        matched_evidence = 0

        for item in evidence:
            if not isinstance(item, dict):
                continue

            description = str(
                item.get("description", "")
            ).strip().lower()

            if description and description in current_evidence_text:
                matched_evidence += 1

        if evidence_count > 0:
            evidence_overlap = matched_evidence / evidence_count
        else:
            evidence_overlap = 0.0

        if evidence_count > 0 and matched_evidence == 0:
            issues.append(
                "Supporting evidence could not be traced to the "
                "current incident inputs."
            )
        elif matched_evidence > 0:
            checks.append(
                f"{matched_evidence} evidence item(s) traceable "
                "to current incident inputs."
            )

        # ---------------------------------------------------------
        # 6. Detect obvious symptom-only root causes
        # ---------------------------------------------------------
        symptom_terms = [
            "latency exceeded",
            "high latency",
            "latency anomaly",
            "request latency",
            "http 500",
            "timeout",
            "slow request",
            "slow span",
        ]

        root_cause_text = str(root_cause).lower()

        symptom_only = any(
            term in root_cause_text
            for term in symptom_terms
        )

        if symptom_only:
            issues.append(
                "The proposed root cause appears to describe "
                "an observed symptom rather than an underlying cause."
            )

        # ---------------------------------------------------------
        # 7. Calculate independent validation confidence
        #
        # Weighted evidence overlap:
        #   40% current-evidence traceability
        #   30% reasoning confidence
        #   20% root-cause presence
        #   10% supporting-evidence presence
        # ---------------------------------------------------------
        root_cause_score = 1.0 if root_cause_present else 0.0
        evidence_presence_score = 1.0 if evidence_count > 0 else 0.0

        validation_confidence = (
            0.40 * evidence_overlap
            + 0.30 * confidence
            + 0.20 * root_cause_score
            + 0.10 * evidence_presence_score
        )

        # Symptom-only diagnoses should not pass validation.
        if symptom_only:
            validation_confidence *= 0.5

        validation_confidence = max(
            0.0,
            min(1.0, validation_confidence),
        )

        checks.append(
            f"Evidence overlap: {evidence_overlap:.2f}."
        )

        checks.append(
            f"Computed validation confidence: "
            f"{validation_confidence:.2f}."
        )

        # ---------------------------------------------------------
        # 8. Check Reasoning Agent confidence
        # A low reasoning confidence always requires human review.
        # ---------------------------------------------------------
        if confidence < self.confidence_threshold:
            issues.append(
                f"Reasoning confidence {confidence:.2f} is below the "
                f"validation threshold {self.confidence_threshold:.2f}."
            )
        else:
            checks.append(
                f"Reasoning confidence {confidence:.2f} meets the "
                f"validation threshold."
            )

        # ---------------------------------------------------------
        # 9. Check computed validation confidence
        # ---------------------------------------------------------
        if validation_confidence < self.confidence_threshold:
            issues.append(
                f"Validation confidence "
                f"{validation_confidence:.2f} is below the "
                f"validation threshold "
                f"{self.confidence_threshold:.2f}."
            )
        else:
            checks.append(
                f"Validation confidence "
                f"{validation_confidence:.2f} meets the "
                f"validation threshold."
            )

        # ---------------------------------------------------------
        # 9. Determine validation result
        # ---------------------------------------------------------
        validated = len(issues) == 0
        requires_human_review = not validated

        if validated:
            summary = "RCA passed validation."
        else:
            summary = "RCA requires validation review."

        findings = []

        if validated:
            findings.append(
                "Root cause is supported by the available evidence."
            )
        else:
            findings.extend(issues)

        return AgentOutput(
            agent=self.name,
            status="completed",
            summary=summary,
            findings=findings,
            evidence=[],
            hypotheses=[],
            confidence=validation_confidence,
            metadata={
                "validated": validated,
                "requires_human_review": requires_human_review,
                "issues": issues,
                "checks": checks,
                "root_cause": root_cause,
                "original_confidence": confidence,
                "validation_confidence": validation_confidence,
                "evidence_overlap": evidence_overlap,
                "matched_evidence": matched_evidence,
                "total_evidence": evidence_count,
            },
        )

