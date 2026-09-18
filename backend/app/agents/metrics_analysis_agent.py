from __future__ import annotations

import json
from typing import Any, Callable

from langchain_core.prompts import ChatPromptTemplate

from .base import BaseAgent


class MetricsAnalysisAgent(BaseAgent):
    """
    Analyzes preprocessed metric anomalies and identifies
    metric-based hypotheses related to an incident.

    Expected output:
    {
        "hypothesis": "...",
        "findings": [
            {
                "metric": "...",
                "value": 0.0,
                "timestamp": "...",
                "service": "...",
                "observation": "...",
                "relevance": "..."
            }
        ],
        "confidence": 0.0
    }
    """

    def __init__(
        self,
        llm: Callable[[str], Any] | None = None,
        name: str = "metrics_analysis_agent",
    ):
        super().__init__(name)
        self.llm = llm

        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
You are a metrics analysis agent in an automated
root-cause-analysis system.

Analyze the provided preprocessed metric anomalies and
correlate them with the incident timeframe.

Identify:
1. Important metric spikes or abnormal trends.
2. Metrics whose timestamps overlap with the incident.
3. Relationships between different metric anomalies.
4. A possible incident hypothesis supported by the metric data.
5. Specific metric evidence supporting the hypothesis.

Return ONLY valid JSON in exactly this structure:

{{
    "hypothesis": "string",
    "findings": [
        {{
            "metric": "string",
            "value": 0.0,
            "timestamp": "string",
            "service": "string",
            "observation": "string",
            "relevance": "string"
        }}
    ],
    "confidence": 0.0
}}

Rules:
- confidence must be between 0.0 and 1.0.
- Use ONLY the supplied metric data.
- Do not invent metric values.
- Do not invent timestamps.
- Do not invent services.
- Explicitly connect important metric spikes to the incident timeframe.
- A finding must be backed by a specific supplied metric data point.
- If there are no metric anomalies, return an empty findings list,
  an appropriate hypothesis, and confidence 0.0.
""",
                ),
                (
                    "human",
                    """
Incident timeframe:
Start: {incident_start}
End: {incident_end}

Preprocessed metric anomalies:
{metrics}
""",
                ),
            ]
        )

    def _format_metrics(
        self,
        metrics: list[dict[str, Any]],
    ) -> str:
        return json.dumps(
            metrics,
            indent=2,
            default=str,
        )

    def _parse_response(
        self,
        response: Any,
    ) -> dict[str, Any]:

        if hasattr(response, "content"):
            response = response.content

        if not isinstance(response, str):
            response = str(response)

        response = response.strip()

        if response.startswith("```"):
            lines = response.splitlines()

            if lines and lines[0].startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            response = "\n".join(lines).strip()

        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            start = response.find("{")
            end = response.rfind("}")

            if start == -1 or end == -1 or end <= start:
                raise

            parsed = json.loads(
                response[start:end + 1]
            )

        if not isinstance(parsed, dict):
            raise ValueError(
                "LLM response must be a JSON object"
            )

        hypothesis = parsed.get("hypothesis", "")
        findings = parsed.get("findings", [])
        confidence = parsed.get("confidence", 0.0)

        if not isinstance(hypothesis, str):
            raise ValueError(
                "hypothesis must be a string"
            )

        if not isinstance(findings, list):
            raise ValueError(
                "findings must be a list"
            )

        confidence = float(confidence)

        if not 0.0 <= confidence <= 1.0:
            raise ValueError(
                "confidence must be between 0.0 and 1.0"
            )

        return {
            "hypothesis": hypothesis,
            "findings": findings,
            "confidence": confidence,
        }

    def run(
        self,
        state: dict[str, Any],
    ) -> dict[str, Any]:

        raw_inputs = state.get("raw_inputs", {})

        metrics = raw_inputs.get(
            "metric_anomalies",
            [],
        )

        incident_start = raw_inputs.get(
            "incident_start",
            "",
        )

        incident_end = raw_inputs.get(
            "incident_end",
            "",
        )

        if not isinstance(metrics, list):
            raise ValueError(
                "raw_inputs.metric_anomalies must be a list"
            )

        if not metrics:
            return {
                "hypothesis": "No metric anomalies were provided for analysis.",
                "findings": [],
                "confidence": 0.0,
            }

        if self.llm is None:
            raise RuntimeError(
                "MetricsAnalysisAgent requires an LLM callable."
            )

        metrics_text = self._format_metrics(metrics)

        messages = self.prompt.format_messages(
            incident_start=incident_start,
            incident_end=incident_end,
            metrics=metrics_text,
        )

        prompt_text = "\n\n".join(
            message.content
            for message in messages
        )

        response = self.llm(prompt_text)

        return self._parse_response(response)
