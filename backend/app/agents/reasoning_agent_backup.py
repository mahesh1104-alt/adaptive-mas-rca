from __future__ import annotations

import json
from typing import Any

from app.agents.state import (
    AgentOutput,
    EvidenceItem,
    FinalReport,
    Hypothesis,
    RankedRootCause,
)
from app.ollama_adapter import ollama_llm


class ReasoningAgent:
    name = "reasoning_agent"

    # ------------------------------------------------------------------
    # JSON PARSING
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_llm_response(response: Any) -> dict[str, Any] | None:
        """
        Parse a JSON object from an LLM response.

        Handles:
        - dict responses
        - normal JSON
        - markdown ```json fences
        - surrounding explanatory text
        - LangChain-style response objects with .content
        - JSON embedded inside surrounding text
        """

        # Direct dictionary response
        if isinstance(response, dict):
            return response

        # LangChain/Ollama message object
        if hasattr(response, "content"):
            response = response.content

        if not isinstance(response, str):
            return None

        text = response.strip()

        if not text:
            return None

        # --------------------------------------------------------------
        # Remove markdown code fences
        # --------------------------------------------------------------

        if text.startswith("```"):
            lines = text.splitlines()

            if lines:
                lines = lines[1:]

            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]

            text = "\n".join(lines).strip()

            # Remove optional "json" marker
            if text.lower().startswith("json"):
                text = text[4:].strip()

        # --------------------------------------------------------------
        # First: parse complete response
        # --------------------------------------------------------------

        try:
            parsed = json.loads(text)

            if isinstance(parsed, dict):
                return parsed

        except (json.JSONDecodeError, TypeError):
            pass

        # --------------------------------------------------------------
        # Second: use JSONDecoder.raw_decode()
        #
        # This is more robust than using rfind("}") because an LLM
        # response may contain extra text after the JSON.
        # --------------------------------------------------------------

        decoder = json.JSONDecoder()

        for index, character in enumerate(text):
            if character != "{":
                continue

            candidate = text[index:]

            try:
                parsed, _ = decoder.raw_decode(candidate)

                if isinstance(parsed, dict):
                    return parsed

            except (json.JSONDecodeError, TypeError):
                continue

        # --------------------------------------------------------------
        # Last fallback: first { ... last }
        # --------------------------------------------------------------

        start = text.find("{")
        end = text.rfind("}")

        if start != -1 and end > start:
            candidate = text[start : end + 1]

            try:
                parsed = json.loads(candidate)

                if isinstance(parsed, dict):
                    return parsed

            except (json.JSONDecodeError, TypeError):
                pass

        return None

    # ------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------

    def __init__(self, llm=None):
        self.llm = llm or ollama_llm

    # ------------------------------------------------------------------
    # LLM INVOCATION
    # ------------------------------------------------------------------

    def _invoke_llm(self, prompt: str) -> Any:
        """Invoke either a LangChain-style LLM or a callable LLM."""

        if hasattr(self.llm, "invoke"):
            return self.llm.invoke(prompt)

        return self.llm(prompt)

    # ------------------------------------------------------------------
    # RETRY PROMPT
    # ------------------------------------------------------------------

    @staticmethod
    def _build_retry_prompt(original_prompt: str) -> str:
        """
        Build a strict retry prompt after malformed structured output.
        """

        return f"""
The previous reasoning response was not valid JSON.

Repeat the reasoning task below.

CRITICAL OUTPUT REQUIREMENTS:

1. Return ONLY one valid JSON object.
2. Do NOT use markdown.
3. Do NOT use ```json fences.
4. Do NOT add explanations before or after the JSON.
5. Use double quotes for every JSON key and string.
6. Do not include trailing commas.
7. Ensure the JSON can be parsed directly by Python json.loads().
8. Follow all RCA evidence rules from the original prompt.
9. If there is insufficient evidence for an underlying root cause:
   - root_cause must be null
   - ranked_root_causes must be []
   - confidence must be 0.0
   - requires_human_review must be true.

ORIGINAL TASK:

{original_prompt}
"""

    # ------------------------------------------------------------------
    # MAIN AGENT
    # ------------------------------------------------------------------

    def run(self, state: dict[str, Any]) -> AgentOutput:
        raw_inputs = state.get("raw_inputs", {})
        agent_outputs = state.get("agent_outputs", {})

        prompt = self._build_prompt(
            raw_inputs,
            agent_outputs,
        )

        # --------------------------------------------------------------
        # First LLM call
        # --------------------------------------------------------------

        try:
            response = self._invoke_llm(prompt)
            data = self._parse_llm_response(response)

        except Exception as exc:
            data = None
            first_error = str(exc)

        else:
            first_error = None

        # --------------------------------------------------------------
        # Retry once if structured output was invalid
        # --------------------------------------------------------------

        retry_used = False

        if data is None:
            retry_used = True

            retry_prompt = self._build_retry_prompt(prompt)

            try:
                retry_response = self._invoke_llm(retry_prompt)
                data = self._parse_llm_response(retry_response)

            except Exception:
                data = None

                # --------------------------------------------------------------
        # Evidence-grounded fallback
        # --------------------------------------------------------------

        grounded_fallback = None

        if data is None:
            grounded_fallback = (
                self._build_evidence_grounded_fallback(
                    agent_outputs
                )
            )

        else:
            model_root_cause = data.get("root_cause")
            model_confidence = self._safe_float(
                data.get("confidence", 0.0)
            )

            # If the LLM produced a structured response but could not
            # establish a root cause, give the deterministic
            # evidence-grounded fallback a chance.
            if (
                not model_root_cause
                or model_confidence <= 0.0
            ):
                grounded_fallback = (
                    self._build_evidence_grounded_fallback(
                        agent_outputs
                    )
                )

        if grounded_fallback is not None:
            data = grounded_fallback

        elif data is None:
            fallback_message = (
                "Reasoning model could not establish an "
                "underlying root cause from the available "
                "current incident evidence."
            )

            if first_error:
                fallback_message = (
                    "Reasoning model failed to produce valid "
                    "structured output and the available "
                    "evidence did not establish an underlying "
                    f"root cause: {first_error}"
                )

            data = {
                "root_cause": None,
                "explanation": fallback_message,
                "confidence": 0.0,
                "supporting_evidence": [],
                "alternative_hypotheses": [],
                "recommended_actions": [],
                "ranked_root_causes": [],
                "requires_human_review": True,
            }

        # --------------------------------------------------------------
        # Normalize and validate the model response
        # --------------------------------------------------------------

        data = self._normalize_reasoning_output(
            data,
            agent_outputs,
        )

        report = self._build_report(
            data,
            agent_outputs,
        )

        metadata = {
            "recommended_actions": report.recommended_actions,
            "requires_human_review": report.requires_human_review,
            "final_report": report.model_dump(),
            "retry_used": retry_used,
        }

        return AgentOutput(
            agent=self.name,
            status="completed",
            summary=report.explanation or "",
            findings=[
                report.root_cause
            ]
            if report.root_cause
            else [],
            evidence=report.supporting_evidence,
            hypotheses=report.alternative_hypotheses,
            confidence=report.confidence,
            metadata=metadata,
        )


    # ------------------------------------------------------------------
    # EVIDENCE-GROUNDED FALLBACK
    # ------------------------------------------------------------------

    def _build_evidence_grounded_fallback(
        self,
        agent_outputs: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Build a deterministic RCA from strong, directly observed
        specialized-agent evidence when the LLM cannot produce a
        usable structured RCA.

        This fallback never uses historical incidents as proof and
        never invents evidence.
        """

        log_output = agent_outputs.get("log_analysis_agent", {})
        metrics_output = agent_outputs.get(
            "metrics_analysis_agent",
            {},
        )
        source_output = agent_outputs.get(
            "source_code_analysis_agent",
            {},
        )
        trace_output = agent_outputs.get(
            "trace_analysis_agent",
            {},
        )

        candidates: list[dict[str, Any]] = []

        # --------------------------------------------------------------
        # 1. Source-code defect
        # --------------------------------------------------------------

        if isinstance(source_output, dict):
            suspect_change = str(
                source_output.get(
                    "suspect_change",
                    "",
                )
                or ""
            ).strip()

            explanation = str(
                source_output.get(
                    "explanation",
                    "",
                )
                or ""
            ).strip()

            source_confidence = self._safe_float(
                source_output.get(
                    "confidence",
                    0.0,
                )
            )

            source_file = source_output.get(
                "file"
            )

            if suspect_change and source_confidence > 0.0:
                candidates.append(
                    {
                        "cause": suspect_change,
                        "confidence": source_confidence,
                        "justification": explanation,
                        "evidence": [
                            {
                                "source_type": "source_code",
                                "source_id": source_file,
                                "timestamp": None,
                                "service": None,
                                "field": "suspect_change",
                                "value": suspect_change,
                                "description": explanation,
                                "relevance": source_confidence,
                                "agent": "source_code_analysis_agent",
                            }
                        ],
                    }
                )

        # --------------------------------------------------------------
        # 2. Database connection-pool exhaustion
        # --------------------------------------------------------------

        if isinstance(log_output, dict):
            anomalies = log_output.get(
                "anomalies",
                [],
            )

            if isinstance(anomalies, list):
                pool_exhaustion = None

                for anomaly in anomalies:
                    if not isinstance(anomaly, dict):
                        continue

                    text = " ".join(
                        str(anomaly.get(field, ""))
                        for field in (
                            "type",
                            "description",
                            "evidence",
                        )
                    ).lower()

                    if (
                        "connection pool exhaustion" in text
                        or "connectionpool exhaustion" in text
                        or "connection pool exhausted" in text
                    ):
                        pool_exhaustion = anomaly
                        break

                if pool_exhaustion is not None:
                    metric_confidence = 0.0

                    if isinstance(metrics_output, dict):
                        findings = metrics_output.get(
                            "findings",
                            [],
                        )

                        if isinstance(findings, list):
                            for finding in findings:
                                if not isinstance(finding, dict):
                                    continue

                                metric_name = str(
                                    finding.get(
                                        "metric",
                                        "",
                                    )
                                ).lower()

                                observation = str(
                                    finding.get(
                                        "observation",
                                        "",
                                    )
                                ).lower()

                                if (
                                    "connection_pool" in metric_name
                                    or "connection pool" in observation
                                ):
                                    metric_confidence = (
                                        self._safe_float(
                                            metrics_output.get(
                                                "confidence",
                                                0.0,
                                            )
                                        )
                                    )
                                    break

                    log_confidence = self._safe_float(
                        log_output.get(
                            "confidence",
                            0.0,
                        )
                    )

                    confidence = max(
                        log_confidence,
                        metric_confidence,
                    )

                    evidence = []

                    evidence.append(
                        {
                            "source_type": "log",
                            "source_id": None,
                            "timestamp": None,
                            "service": pool_exhaustion.get(
                                "service"
                            ),
                            "field": "anomaly",
                            "value": pool_exhaustion,
                            "description": (
                                pool_exhaustion.get(
                                    "evidence"
                                )
                                or pool_exhaustion.get(
                                    "description"
                                )
                            ),
                            "relevance": log_confidence,
                            "agent": "log_analysis_agent",
                        }
                    )

                    if isinstance(metrics_output, dict):
                        findings = metrics_output.get(
                            "findings",
                            [],
                        )

                        if isinstance(findings, list):
                            for finding in findings:
                                if not isinstance(finding, dict):
                                    continue

                                metric_name = str(
                                    finding.get(
                                        "metric",
                                        "",
                                    )
                                ).lower()

                                if "connection_pool" not in metric_name:
                                    continue

                                evidence.append(
                                    {
                                        "source_type": "metric",
                                        "source_id": metric_name,
                                        "timestamp": finding.get(
                                            "timestamp"
                                        ),
                                        "service": finding.get(
                                            "service"
                                        ),
                                        "field": finding.get(
                                            "metric"
                                        ),
                                        "value": finding.get(
                                            "value"
                                        ),
                                        "description": finding.get(
                                            "observation"
                                        ),
                                        "relevance": metric_confidence,
                                        "agent": (
                                            "metrics_analysis_agent"
                                        ),
                                    }
                                )

                                break

                    candidates.append(
                        {
                            "cause": (
                                "Database connection pool "
                                "exhaustion"
                            ),
                            "confidence": confidence,
                            "justification": (
                                "Current log evidence identifies "
                                "connection pool exhaustion, and "
                                "the metrics evidence shows "
                                "connection pool usage at a critical "
                                "level."
                            ),
                            "evidence": evidence,
                        }
                    )

        # --------------------------------------------------------------
        # 3. Memory exhaustion
        # --------------------------------------------------------------

        if isinstance(log_output, dict):
            anomalies = log_output.get("anomalies", [])

            if isinstance(anomalies, list):
                memory_exhaustion = None

                for anomaly in anomalies:
                    if not isinstance(anomaly, dict):
                        continue

                    text = " ".join(
                        str(anomaly.get(field, ""))
                        for field in (
                            "type",
                            "description",
                            "evidence",
                        )
                    ).lower()

                    if (
                        "out of memory" in text
                        or "memory exhaustion" in text
                        or "memory exhausted" in text
                    ):
                        memory_exhaustion = anomaly
                        break

                if memory_exhaustion is not None:
                    log_confidence = self._safe_float(
                        log_output.get("confidence", 0.0)
                    )

                    metric_confidence = 0.0

                    if isinstance(metrics_output, dict):
                        findings = metrics_output.get("findings", [])

                        if isinstance(findings, list):
                            for finding in findings:
                                if not isinstance(finding, dict):
                                    continue

                                metric_name = str(
                                    finding.get("metric", "")
                                ).lower()

                                if "memory" in metric_name:
                                    metric_confidence = (
                                        self._safe_float(
                                            metrics_output.get(
                                                "confidence",
                                                0.0,
                                            )
                                        )
                                    )
                                    break

                    confidence = max(
                        log_confidence,
                        metric_confidence,
                    )

                    evidence = [
                        {
                            "source_type": "log",
                            "source_id": None,
                            "timestamp": memory_exhaustion.get(
                                "timestamp"
                            ),
                            "service": memory_exhaustion.get(
                                "service"
                            ),
                            "field": "anomaly",
                            "value": memory_exhaustion,
                            "description": (
                                memory_exhaustion.get("evidence")
                                or memory_exhaustion.get("description")
                            ),
                            "relevance": log_confidence,
                            "agent": "log_analysis_agent",
                        }
                    ]

                    if isinstance(metrics_output, dict):
                        findings = metrics_output.get(
                            "findings",
                            [],
                        )

                        if isinstance(findings, list):
                            for finding in findings:
                                if not isinstance(finding, dict):
                                    continue

                                metric_name = str(
                                    finding.get("metric", "")
                                ).lower()

                                if "memory" not in metric_name:
                                    continue

                                evidence.append(
                                    {
                                        "source_type": "metric",
                                        "source_id": metric_name,
                                        "timestamp": finding.get(
                                            "timestamp"
                                        ),
                                        "service": finding.get(
                                            "service"
                                        ),
                                        "field": finding.get(
                                            "metric"
                                        ),
                                        "value": finding.get(
                                            "value"
                                        ),
                                        "description": finding.get(
                                            "observation"
                                        ),
                                        "relevance": metric_confidence,
                                        "agent": (
                                            "metrics_analysis_agent"
                                        ),
                                    }
                                )
                                break

                    candidates.append(
                        {
                            "cause": (
                                "Memory exhaustion in "
                                f"{memory_exhaustion.get('service', 'service')}"
                            ),
                            "confidence": confidence,
                            "justification": (
                                "Current log evidence identifies an "
                                "out-of-memory condition, and the "
                                "memory metric confirms critically high "
                                "memory utilization."
                            ),
                            "evidence": evidence,
                        }
                    )

        # --------------------------------------------------------------
        # 4. Do not turn a bare trace failure into a root cause.
        # --------------------------------------------------------------
        # A failing trace by itself is a symptom, not an underlying
        # root cause. Therefore no RCA candidate is created from trace
        # output alone.

        # --------------------------------------------------------------
        # Select strongest current-evidence candidate
        # --------------------------------------------------------------

        if not candidates:
            return None

        candidates.sort(
            key=lambda item: item.get(
                "confidence",
                0.0,
            ),
            reverse=True,
        )

        selected = candidates[0]

        confidence = max(
            0.0,
            min(
                1.0,
                self._safe_float(
                    selected.get(
                        "confidence",
                        0.0,
                    )
                ),
            ),
        )

        if confidence <= 0.0:
            return None

        return {
            "root_cause": selected["cause"],
            "explanation": selected["justification"],
            "confidence": confidence,
            "supporting_evidence": selected["evidence"],
            "alternative_hypotheses": [],
            "recommended_actions": [],
            "ranked_root_causes": [
                {
                    "rank": 1,
                    "cause": selected["cause"],
                    "justification": selected["justification"],
                    "confidence": confidence,
                    "supporting_evidence": selected["evidence"],
                }
            ],
            "requires_human_review": confidence < 0.70,
        }

    # ------------------------------------------------------------------
    # OUTPUT NORMALIZATION
    # ------------------------------------------------------------------

    def _normalize_reasoning_output(
        self,
        data: dict[str, Any],
        agent_outputs: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Enforce consistency rules after the LLM response.

        The LLM remains responsible for RCA reasoning, but this layer
        prevents internally contradictory reports from reaching the
        final pipeline.
        """

        normalized = dict(data)
        # If the current incident has no established root cause,
        # never allow the LLM to promote a symptom into an RCA.
        if not normalized.get("root_cause"):
            normalized["confidence"] = 0.0
            normalized["ranked_root_causes"] = []
            normalized["requires_human_review"] = True

        root_cause = normalized.get("root_cause")

        confidence = self._safe_float(
            normalized.get("confidence", 0.0)
        )

        # Reject known symptom-only root causes.
        symptom_terms = (
            "latency",
            "timeout",
            "timed out",
            "slo violation",
            "high cpu",
            "http 500",
            "http 504",
            "failed request",
            "slow request",
            "slow span",
        )

        root_cause_text = str(root_cause or "").lower()

        if any(term in root_cause_text for term in symptom_terms):
            # Allow a concrete source-code defect to override a
            # symptom-only LLM conclusion.
            source_output = agent_outputs.get(
                "source_code_analysis_agent", {}
            )

            suspect_change = str(
                source_output.get("suspect_change", "")
                if isinstance(source_output, dict)
                else ""
            ).strip()

            source_confidence = self._safe_float(
                source_output.get("confidence", 0.0)
                if isinstance(source_output, dict)
                else 0.0
            )

            if suspect_change and source_confidence > 0.0:
                root_cause = suspect_change
                confidence = source_confidence
                requires_human_review = source_confidence < 0.70

                normalized["explanation"] = (
                    source_output.get("explanation")
                    or "A concrete source-code defect supports the root cause."
                )

                normalized["ranked_root_causes"] = [
                    {
                        "rank": 1,
                        "cause": root_cause,
                        "justification": normalized["explanation"],
                        "confidence": confidence,
                        "supporting_evidence": source_output.get(
                            "evidence", []
                        ),
                    }
                ]
            else:
                root_cause = None
                confidence = 0.0
                ranked = []
                requires_human_review = True
            normalized["explanation"] = (
                "The available evidence identifies a symptom "
                "but does not establish its underlying cause."
            )

        requires_human_review = bool(
            normalized.get(
                "requires_human_review",
                False,
            )
        )

        ranked = normalized.get(
            "ranked_root_causes",
            [],
        )

        if not isinstance(ranked, list):
            ranked = []

        supporting_evidence = normalized.get(
            "supporting_evidence",
            [],
        )

        if not isinstance(supporting_evidence, list):
            supporting_evidence = []

        # --------------------------------------------------------------
        # If confidence is zero, a concrete root cause should not be
        # presented as established.
        # --------------------------------------------------------------

        if confidence <= 0.0 and root_cause:
            root_cause = None
            ranked = []
            requires_human_review = True

            normalized["explanation"] = (
                normalized.get("explanation")
                or "The available evidence does not establish "
                "an underlying root cause."
            )

        # --------------------------------------------------------------
        # If the model explicitly requires human review with zero
        # confidence, do not preserve a concrete root cause.
        # --------------------------------------------------------------

        if requires_human_review and confidence <= 0.0:
            root_cause = None
            ranked = []

        # --------------------------------------------------------------
        # Ranked-root-cause consistency
        # --------------------------------------------------------------

        if root_cause and ranked:
            first_candidate = ranked[0]

            if isinstance(first_candidate, dict):
                candidate_cause = first_candidate.get("cause")

                if candidate_cause:
                    # Rank 1 must match the root_cause.
                    if str(candidate_cause).strip() != str(
                        root_cause
                    ).strip():
                        first_candidate["cause"] = root_cause

        # --------------------------------------------------------------
        # If root_cause is null, ranked candidates must also be empty.
        # --------------------------------------------------------------

        if not root_cause:
            ranked = []
            confidence = 0.0
            requires_human_review = True

        normalized["root_cause"] = root_cause
        normalized["confidence"] = max(
            0.0,
            min(1.0, confidence),
        )
        normalized["ranked_root_causes"] = ranked
        normalized["supporting_evidence"] = supporting_evidence
        normalized["requires_human_review"] = (
            requires_human_review
        )

        return normalized

    # ------------------------------------------------------------------
    # SAFE FLOAT
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    # ------------------------------------------------------------------
    # RCA PROMPT
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        raw_inputs: dict[str, Any],
        agent_outputs: dict[str, Any],
    ) -> str:
        return f"""
You are the Reasoning Agent in a distributed-system
Root Cause Analysis pipeline.

Your task is to combine the findings from multiple
specialized agents and determine the most supported
root cause of the CURRENT incident.

IMPORTANT RULES:

1. Identify the EARLIEST actual failure.

2. Distinguish root cause from downstream symptoms.

3. Use timestamps and service names to reconstruct
   failure propagation.

4. Do not automatically classify a timeout as a network failure.

5. Only claim a network problem when there is actual evidence.

6. Do not invent evidence.

7. Current incident evidence has higher priority than
   historical evidence.

8. Historical incidents are supporting evidence only.

9. Do not copy a historical root cause unless current
   evidence supports it.

10. Metrics are evidence only when marked as anomalies.

11. Correlation alone does not prove causation.

12. If evidence is insufficient to establish an underlying
    cause, do NOT label an observed symptom or anomaly as
    the root cause. Reduce confidence and require human review.

13. Distinguish causes from symptoms. High CPU, high latency,
    HTTP 500 errors, timeouts, and failed requests may be
    symptoms unless another piece of evidence explains why
    they occurred.

14. Do not claim that one anomaly caused another merely because
    they occurred at the same time.

15. Prefer a concrete underlying cause such as a database issue,
    code defect, resource exhaustion, dependency failure, or
    configuration problem only when current evidence supports it.

15a. Do NOT treat high CPU, high latency, HTTP 500 errors,
     timeouts, or failed requests as an underlying root cause
     by themselves. These are symptoms unless current evidence
     identifies what caused the anomaly.

15b. A metric anomaly can support a root-cause hypothesis,
     but the anomaly itself is not sufficient to establish
     causation.

15c. If the strongest evidence only shows that a service is
     unhealthy, rank that observation as a symptom/hypothesis
     with low confidence rather than presenting it as a proven
     underlying root cause.

16. If the available evidence only proves that a service is
    unhealthy but does not establish the underlying cause,
    explicitly state that the root cause is undetermined and
    set requires_human_review to true.

17. Historical retrieval results may suggest hypotheses, but
    they must never be treated as proof of the current root cause.

18. Every supporting evidence item must correspond to evidence
    actually present in the current incident or specialized
    agent findings.

19. NEVER invent timestamps, services, source IDs, metric fields,
    trace IDs, or evidence descriptions.

20. When selecting supporting evidence, copy the actual evidence
    fields from the specialized agent findings whenever possible.

21. A source-code finding identifying a concrete defect can be
    stronger evidence than a symptom such as high CPU or latency.

22. A concrete dependency failure can support a dependency-related
    root cause, but a timeout alone does not prove why the timeout
    happened.

CURRENT INCIDENT INPUTS:

{json.dumps(raw_inputs, indent=2, default=str)}

SPECIALIZED AGENT FINDINGS:

{json.dumps(agent_outputs, indent=2, default=str)}

Return ONLY valid JSON in this format:

{{
  "root_cause": "most supported root cause",
  "explanation": "why the evidence supports this conclusion",
  "confidence": 0.0,

  "ranked_root_causes": [
    {{
      "rank": 1,
      "cause": "most supported candidate root cause",
      "justification": "why this candidate is supported by the evidence",
      "confidence": 0.0,
      "supporting_evidence": []
    }},
    {{
      "rank": 2,
      "cause": "second most supported candidate root cause",
      "justification": "why this candidate is plausible but weaker",
      "confidence": 0.0,
      "supporting_evidence": []
    }}
  ],

  "supporting_evidence": [],
  "alternative_hypotheses": [],
  "recommended_actions": [],
  "requires_human_review": false
}}

RANKING RULES:

- Rank candidates from strongest to weakest evidence.

- Rank 1 must correspond to the root_cause field.

- The root_cause should identify an underlying cause, not merely
  an observed symptom or metric anomaly.

- If the underlying cause cannot be established from current
  evidence, set root_cause to null, return an empty
  ranked_root_causes list, set confidence to 0.0, and set
  requires_human_review to true.

- Each candidate must include a concrete justification.

- Each candidate confidence must be between 0.0 and 1.0.

- Supporting evidence must come from the CURRENT incident or
  specialized agent findings.

- Do not create candidates merely because they appeared in
  historical incidents.

- If only one root cause is adequately supported, return one
  ranked candidate rather than inventing additional candidates.

- If no underlying root cause is adequately supported, return
  an empty ranked_root_causes list and set
  requires_human_review to true.
"""

    # ------------------------------------------------------------------
    # FINAL REPORT BUILDING
    # ------------------------------------------------------------------

    def _build_report(
        self,
        data: dict[str, Any],
        agent_outputs: dict[str, Any],
    ) -> FinalReport:

        supporting_evidence: list[EvidenceItem] = []

        # --------------------------------------------------------------
        # Supporting evidence
        # --------------------------------------------------------------

        for item in data.get(
            "supporting_evidence",
            [],
        ):
            if not isinstance(item, dict):
                continue

            try:
                supporting_evidence.append(
                    EvidenceItem(
                        source_type=item.get(
                            "source_type",
                            "reasoning",
                        ),
                        source_id=item.get(
                            "source_id"
                        ),
                        timestamp=item.get(
                            "timestamp"
                        ),
                        service=item.get(
                            "service"
                        ),
                        field=item.get(
                            "field"
                        ),
                        value=item.get(
                            "value"
                        ),
                        description=item.get(
                            "description",
                            str(item),
                        ),
                        relevance=max(
                            0.0,
                            min(
                                1.0,
                                self._safe_float(
                                    item.get(
                                        "relevance",
                                        0.0,
                                    )
                                ),
                            ),
                        ),
                        agent=item.get(
                            "agent",
                            self.name,
                        ),
                    )
                )

            except Exception:
                continue

        # --------------------------------------------------------------
        # Ranked root causes
        # --------------------------------------------------------------

        ranked_root_causes: list[RankedRootCause] = []

        for item in data.get(
            "ranked_root_causes",
            [],
        ):
            if not isinstance(item, dict):
                continue

            try:
                candidate_evidence: list[
                    EvidenceItem
                ] = []

                for evidence in item.get(
                    "supporting_evidence",
                    [],
                ):
                    if not isinstance(evidence, dict):
                        continue

                    try:
                        candidate_evidence.append(
                            EvidenceItem(
                                source_type=evidence.get(
                                    "source_type",
                                    "reasoning",
                                ),
                                source_id=evidence.get(
                                    "source_id"
                                ),
                                timestamp=evidence.get(
                                    "timestamp"
                                ),
                                service=evidence.get(
                                    "service"
                                ),
                                field=evidence.get(
                                    "field"
                                ),
                                value=evidence.get(
                                    "value"
                                ),
                                description=evidence.get(
                                    "description",
                                    str(evidence),
                                ),
                                relevance=max(
                                    0.0,
                                    min(
                                        1.0,
                                        self._safe_float(
                                            evidence.get(
                                                "relevance",
                                                0.0,
                                            )
                                        ),
                                    ),
                                ),
                                agent=evidence.get(
                                    "agent",
                                    self.name,
                                ),
                            )
                        )

                    except Exception:
                        continue

                confidence_value = max(
                    0.0,
                    min(
                        1.0,
                        self._safe_float(
                            item.get(
                                "confidence",
                                0.0,
                            )
                        ),
                    ),
                )

                ranked_root_causes.append(
                    RankedRootCause(
                        rank=int(
                            item.get(
                                "rank",
                                len(
                                    ranked_root_causes
                                )
                                + 1,
                            )
                        ),
                        cause=str(
                            item.get(
                                "cause",
                                "",
                            )
                        ),
                        justification=str(
                            item.get(
                                "justification",
                                "",
                            )
                        ),
                        confidence=confidence_value,
                        supporting_evidence=candidate_evidence,
                    )
                )

            except Exception:
                continue

        # Sort by rank
        ranked_root_causes.sort(
            key=lambda item: item.rank
        )

        # --------------------------------------------------------------
        # Alternative hypotheses
        # --------------------------------------------------------------

        alternatives: list[Hypothesis] = []

        for item in data.get(
            "alternative_hypotheses",
            [],
        ):
            if not isinstance(item, dict):
                continue

            try:
                alternatives.append(
                    Hypothesis(
                        hypothesis_id=str(
                            item.get(
                                "hypothesis_id",
                                f"alternative_"
                                f"{len(alternatives) + 1}",
                            )
                        ),
                        statement=item.get(
                            "statement",
                            "",
                        ),
                        category=item.get(
                            "category"
                        ),
                        confidence=max(
                            0.0,
                            min(
                                1.0,
                                self._safe_float(
                                    item.get(
                                        "confidence",
                                        0.0,
                                    )
                                ),
                            ),
                        ),
                        supporting_evidence=[],
                        contributing_agents=item.get(
                            "contributing_agents",
                            [],
                        ),
                    )
                )

            except Exception:
                continue

        # --------------------------------------------------------------
        # Confidence
        # --------------------------------------------------------------

        confidence = max(
            0.0,
            min(
                1.0,
                self._safe_float(
                    data.get(
                        "confidence",
                        0.0,
                    )
                ),
            ),
        )

        # --------------------------------------------------------------
        # Contributing agents
        # --------------------------------------------------------------

        contributing_agents = list(
            agent_outputs.keys()
        )

        # --------------------------------------------------------------
        # Recommended actions
        # --------------------------------------------------------------

        recommended_actions: list[str] = []

        for action in data.get(
            "recommended_actions",
            [],
        ):
            if isinstance(action, str):
                recommended_actions.append(
                    action
                )

            elif isinstance(action, dict):
                action_text = action.get(
                    "action"
                )

                if action_text:
                    recommended_actions.append(
                        str(action_text)
                    )

        # --------------------------------------------------------------
        # Root cause
        # --------------------------------------------------------------

        root_cause = data.get(
            "root_cause"
        )

        if root_cause is not None:
            root_cause = str(
                root_cause
            ).strip()

            if not root_cause:
                root_cause = None

        # --------------------------------------------------------------
        # If evidence exists only inside Rank 1, promote it.
        # --------------------------------------------------------------

        if (
            not supporting_evidence
            and ranked_root_causes
        ):
            supporting_evidence = list(
                ranked_root_causes[
                    0
                ].supporting_evidence
            )

        # --------------------------------------------------------------
        # Final consistency rule
        #
        # A null root cause means:
        # - confidence = 0
        # - no ranked root causes
        # - human review required
        # --------------------------------------------------------------

        requires_human_review = bool(
            data.get(
                "requires_human_review",
                False,
            )
        )

        if not root_cause:
            root_cause = None
            confidence = 0.0
            ranked_root_causes = []
            requires_human_review = True

        # --------------------------------------------------------------
        # Ensure Rank 1 matches top-level root cause
        # --------------------------------------------------------------

        if (
            root_cause
            and ranked_root_causes
        ):
            ranked_root_causes[0] = (
                ranked_root_causes[0].model_copy(
                    update={
                        "cause": root_cause,
                        "rank": 1,
                    }
                )
            )

        return FinalReport(
            root_cause=root_cause,
            ranked_root_causes=ranked_root_causes,
            explanation=data.get(
                "explanation"
            ),
            confidence=confidence,
            supporting_evidence=supporting_evidence,
            alternative_hypotheses=alternatives,
            contributing_agents=contributing_agents,
            recommended_actions=recommended_actions,
            requires_human_review=(
                requires_human_review
            ),
        )