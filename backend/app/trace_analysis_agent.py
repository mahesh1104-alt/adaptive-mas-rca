"""
Trace Analysis Agent for Adaptive MAS RCA.

Takes a preprocessed trace summary and identifies the service/span
responsible for latency or failure.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================
# STRUCTURED OUTPUT
# ============================================================

class TraceFaultLocalization(BaseModel):
    service: str = Field(..., description="Suspected faulty service")
    span: str = Field(..., description="Suspected faulty span/operation")
    issue_type: str = Field(..., description="failure or latency")
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: List[str] = Field(default_factory=list)


# ============================================================
# PROMPT
# ============================================================

TRACE_ANALYSIS_PROMPT = """
You are a Trace Analysis Agent in a Root Cause Analysis system.

Analyze the preprocessed trace summary below.

Your task is to identify the service and span most responsible for:
1. A failure, if an error span exists.
2. Otherwise, a latency bottleneck.

Use the provided evidence such as:
- error spans
- failed spans
- slow spans
- critical path
- span durations
- HTTP status codes
- error messages

Return ONLY valid JSON in this format:

{{
    "service": "service-name",
    "span": "span-operation",
    "issue_type": "failure",
    "confidence": 0.95,
    "evidence": [
        "evidence 1",
        "evidence 2"
    ]
}}

The issue_type must be either "failure" or "latency".
confidence must be between 0 and 1.

Trace summary:
{trace_summary}
"""


# ============================================================
# AGENT
# ============================================================

class TraceAnalysisAgent:
    """
    Trace analysis agent.

    The LLM client must provide an `invoke(prompt)` method.
    """

    def __init__(self, llm: Any = None):
        self.llm = llm

    def analyze(
        self,
        trace_summary: Dict[str, Any],
    ) -> TraceFaultLocalization:
        """
        Analyze a preprocessed trace summary.
        """

        if not isinstance(trace_summary, dict):
            raise ValueError("trace_summary must be a dictionary")

        if not trace_summary.get("spans"):
            raise ValueError("trace_summary contains no spans")

        # ----------------------------------------------------
        # If no LLM is configured, use deterministic evidence
        # already produced by trace preprocessing.
        # ----------------------------------------------------
        if self.llm is None:
            return self._deterministic_analysis(trace_summary)

        prompt = TRACE_ANALYSIS_PROMPT.format(
            trace_summary=json.dumps(
                trace_summary,
                indent=2,
                default=str,
            )
        )

        response = self.llm.invoke(prompt)

        if hasattr(response, "content"):
            response = response.content

        return self._parse_response(
            response,
            trace_summary,
        )

    # --------------------------------------------------------
    # DETERMINISTIC FALLBACK
    # --------------------------------------------------------

    def _deterministic_analysis(
        self,
        trace_summary: Dict[str, Any],
    ) -> TraceFaultLocalization:

        failing_span = trace_summary.get("failing_span")

        if failing_span:
            evidence = [
                f"Span status is {failing_span.get('status', 'ERROR')}.",
                (
                    f"Service '{failing_span.get('service')}' "
                    f"contains the failing span."
                ),
            ]

            tags = failing_span.get("tags", {})

            if tags.get("http.status_code"):
                evidence.append(
                    f"HTTP status code is {tags['http.status_code']}."
                )

            if tags.get("error.message"):
                evidence.append(
                    f"Error message: {tags['error.message']}"
                )

            return TraceFaultLocalization(
                service=failing_span.get(
                    "service",
                    "unknown-service",
                ),
                span=failing_span.get(
                    "operation",
                    "unknown-operation",
                ),
                issue_type="failure",
                confidence=0.95,
                evidence=evidence,
            )

        # ----------------------------------------------------
        # No failure → analyze latency
        # ----------------------------------------------------

        bottleneck = trace_summary.get("bottleneck_span")

        if not bottleneck:
            slow_spans = trace_summary.get("slow_spans", [])

            if slow_spans:
                bottleneck = max(
                    slow_spans,
                    key=lambda span: float(
                        span.get("duration_ms", 0)
                    ),
                )

        if not bottleneck:
            raise ValueError(
                "Unable to identify a latency bottleneck"
            )

        duration = float(
            bottleneck.get("duration_ms", 0)
        )

        evidence = [
            (
                f"Span duration is {duration:.2f} ms, "
                "making it the primary latency bottleneck."
            )
        ]

        return TraceFaultLocalization(
            service=bottleneck.get(
                "service",
                "unknown-service",
            ),
            span=bottleneck.get(
                "operation",
                "unknown-operation",
            ),
            issue_type="latency",
            confidence=0.90,
            evidence=evidence,
        )

    # --------------------------------------------------------
    # RESPONSE PARSER
    # --------------------------------------------------------

    def _parse_response(
        self,
        response: Any,
        trace_summary: Dict[str, Any],
    ) -> TraceFaultLocalization:

        if not isinstance(response, str):
            response = str(response)

        response = response.strip()

        # Remove markdown JSON fences if the LLM adds them.
        response = re.sub(
            r"^```json\s*",
            "",
            response,
            flags=re.IGNORECASE,
        )

        response = re.sub(
            r"^```\s*",
            "",
            response,
        )

        response = re.sub(
            r"\s*```$",
            "",
            response,
        )

        try:
            data = json.loads(response)

        except json.JSONDecodeError:
            # ------------------------------------------------
            # LLM did not return valid JSON.
            # Fall back to deterministic trace evidence
            # instead of crashing the complete RCA graph.
            # ------------------------------------------------
            return self._deterministic_analysis(trace_summary)

        return TraceFaultLocalization.model_validate(data)


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def analyze_trace(
    trace_summary: Dict[str, Any],
    llm: Any = None,
) -> Dict[str, Any]:
    """
    Analyze a preprocessed trace and return a dictionary.
    """

    agent = TraceAnalysisAgent(llm=llm)

    result = agent.analyze(trace_summary)

    return result.model_dump()


__all__ = [
    "TraceFaultLocalization",
    "TraceAnalysisAgent",
    "analyze_trace",
]