from __future__ import annotations

import json
from typing import Any, Callable

from langchain_core.prompts import ChatPromptTemplate

from .base import BaseAgent


class LogAnalysisAgent(BaseAgent):
    """
    Analyzes preprocessed logs and identifies log-based anomalies.

    Expected output:
        {
            "anomalies": [...],
            "summary": "...",
            "confidence": 0.0-1.0
        }
    """

    def __init__(
        self,
        llm: Callable[[str], Any] | None = None,
        name: str = "log_analysis_agent",
    ):
        super().__init__(name)
        self.llm = llm

        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
You are a log analysis agent in an automated
root-cause-analysis system.

Analyze the provided preprocessed application logs.

Identify:
1. Error patterns
2. Repeated failures
3. Suspicious or anomalous behavior
4. Important services involved
5. Possible indicators of the underlying incident

Return ONLY valid JSON in exactly this structure:

{{
    "anomalies": [
        {{
            "type": "string",
            "service": "string",
            "description": "string",
            "severity": "low|medium|high|critical",
            "evidence": "string"
        }}
    ],
    "summary": "string",
    "confidence": 0.0
}}

Rules:
- confidence must be between 0.0 and 1.0.
- Do not invent log events.
- Base findings only on the supplied logs.
- If no anomaly is present, return an empty anomalies list.
""",
                ),
                (
                    "human",
                    "Preprocessed logs:\n{logs}",
                ),
            ]
        )

    def _format_logs(self, logs: list[dict[str, Any]]) -> str:
        return json.dumps(
            logs,
            indent=2,
            default=str,
        )

    def _parse_response(self, response: Any) -> dict[str, Any]:
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
            raise ValueError("LLM response must be a JSON object")

        anomalies = parsed.get("anomalies", [])
        summary = parsed.get("summary", "")
        confidence = parsed.get("confidence", 0.0)

        if not isinstance(anomalies, list):
            raise ValueError("anomalies must be a list")

        if not isinstance(summary, str):
            raise ValueError("summary must be a string")

        confidence = float(confidence)

        if not 0.0 <= confidence <= 1.0:
            raise ValueError(
                "confidence must be between 0.0 and 1.0"
            )

        return {
            "anomalies": anomalies,
            "summary": summary,
            "confidence": confidence,
        }

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        logs = state.get("raw_inputs", {}).get("logs", [])

        if not isinstance(logs, list):
            raise ValueError("raw_inputs.logs must be a list")

        if not logs:
            return {
                "anomalies": [],
                "summary": "No logs were provided for analysis.",
                "confidence": 0.0,
            }

        if self.llm is None:
            raise RuntimeError(
                "LogAnalysisAgent requires an LLM callable."
            )

        logs_text = self._format_logs(logs)

        messages = self.prompt.format_messages(
            logs=logs_text
        )

        prompt_text = "\n\n".join(
            message.content
            for message in messages
        )

        response = self.llm(prompt_text)

        return self._parse_response(response)