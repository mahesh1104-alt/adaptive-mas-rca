"""
Source Code Analysis Agent.

Analyzes source-code snippets and recent commits to identify suspicious
code changes that may contribute to an incident.
"""

import json
import logging
from typing import Any, Dict, List

from .base import BaseAgent


logger = logging.getLogger(__name__)


class SourceCodeAnalysisAgent(BaseAgent):
    """
    Specialized agent for source-code and recent-commit analysis.

    Expected raw_inputs:
        source_snippets: list[dict]
        recent_commits: list[dict]

    Expected LLM response:
        {
            "suspect_change": "...",
            "file": "...",
            "line_start": 1,
            "line_end": 2,
            "commit_sha": "...",
            "explanation": "...",
            "confidence": 0.0
        }
    """

    def __init__(self, llm=None):
        super().__init__("source_code_analysis_agent")
        self.llm = llm

    # ==================================================================
    # PROMPT
    # ==================================================================

    def _build_prompt(
        self,
        source_snippets: List[Dict[str, Any]],
        recent_commits: List[Dict[str, Any]],
    ) -> str:
        """Build the LLM prompt."""

        snippets_text = json.dumps(
            source_snippets,
            indent=2,
            default=str,
        )

        commits_text = json.dumps(
            recent_commits,
            indent=2,
            default=str,
        )

        return f"""
You are the Source Code Analysis Agent in a multi-agent
Root Cause Analysis system.

Your task is to analyze source-code snippets and recent commits
and identify the code change most likely related to the incident.

SOURCE CODE SNIPPETS:
{snippets_text}

RECENT COMMITS:
{commits_text}

Analyze the supplied source code and commits for:

1. Suspicious code changes.
2. Possible bugs or regressions.
3. Code that could explain the incident.
4. The most relevant recent commit.
5. The relevant file and line range.
6. Why the code may contribute to the incident.
7. A confidence score between 0.0 and 1.0.

Return ONLY one valid JSON object.

Required format:

{{
    "suspect_change": "description of the suspicious change",
    "file": "source file path",
    "line_start": 1,
    "line_end": 2,
    "commit_sha": "commit identifier",
    "explanation": "why this change may contribute to the incident",
    "confidence": 0.0
}}

Rules:
- confidence MUST be between 0.0 and 1.0 inclusive.
- line_start MUST be an integer.
- line_end MUST be an integer.
- Return ONLY JSON.
- Do not return Markdown.
- Do not return ```json fences.
- Do not include additional text before or after the JSON object.
""".strip()

    # ==================================================================
    # FORMATTING HELPERS
    # ==================================================================

    def _format_source_snippets(
        self,
        source_snippets: List[Dict[str, Any]],
    ) -> str:
        """Format source snippets as JSON."""

        return json.dumps(
            source_snippets,
            indent=2,
            default=str,
        )

    def _format_commits(
        self,
        recent_commits: List[Dict[str, Any]],
    ) -> str:
        """Format recent commits as JSON."""

        return json.dumps(
            recent_commits,
            indent=2,
            default=str,
        )

    # ==================================================================
    # RESPONSE PARSING
    # ==================================================================

    def _parse_response(
        self,
        response: Any,
    ) -> Dict[str, Any]:
        """
        Parse and validate the LLM response.

        Supports:
        - normal JSON
        - LangChain/Ollama message objects
        - Markdown ```json fences
        - explanatory text surrounding a JSON object

        Truly malformed JSON still raises JSONDecodeError / ValueError
        so existing tests and graph-level error handling remain intact.
        """

        # --------------------------------------------------------------
        # Extract content from LangChain/Ollama message objects.
        # --------------------------------------------------------------

        if hasattr(response, "content"):
            response = response.content

        if not isinstance(response, str):
            response = str(response)

        response = response.strip()

        if not response:
            raise ValueError(
                "Source Code Analysis Agent response is empty."
            )

        # --------------------------------------------------------------
        # Remove optional Markdown fences.
        # --------------------------------------------------------------

        if response.startswith("```"):
            lines = response.splitlines()

            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            response = "\n".join(lines).strip()

            # Remove optional "json" marker.
            if response.lower().startswith("json"):
                response = response[4:].strip()

        # --------------------------------------------------------------
        # First attempt:
        # Parse the complete response directly.
        # --------------------------------------------------------------

        try:
            parsed = json.loads(response)

        except json.JSONDecodeError:
            parsed = None

        if parsed is not None:
            if not isinstance(parsed, dict):
                raise ValueError(
                    "Source Code Analysis Agent response must "
                    "be a JSON object."
                )

        # --------------------------------------------------------------
        # Second attempt:
        # Extract the first valid JSON object from surrounding text.
        #
        # This handles responses such as:
        #
        # Here is the analysis:
        # {"suspect_change": "...", ...}
        #
        # without accepting genuinely invalid JSON.
        # --------------------------------------------------------------

        if parsed is None:
            decoder = json.JSONDecoder()

            found_object = False

            for index, character in enumerate(response):
                if character != "{":
                    continue

                candidate = response[index:]

                try:
                    parsed_candidate, _ = decoder.raw_decode(
                        candidate
                    )

                except json.JSONDecodeError:
                    continue

                if isinstance(parsed_candidate, dict):
                    parsed = parsed_candidate
                    found_object = True
                    break

            if not found_object:
                # Preserve the original JSON parsing behaviour.
                # This intentionally raises JSONDecodeError.
                parsed = json.loads(response)

        # --------------------------------------------------------------
        # Final type validation.
        # --------------------------------------------------------------

        if not isinstance(parsed, dict):
            raise ValueError(
                "Source Code Analysis Agent response must "
                "be a JSON object."
            )

        # --------------------------------------------------------------
        # Required fields.
        # --------------------------------------------------------------

        required_fields = [
            "suspect_change",
            "file",
            "line_start",
            "line_end",
            "commit_sha",
            "explanation",
            "confidence",
        ]

        missing_fields = [
            field
            for field in required_fields
            if field not in parsed
        ]

        if missing_fields:
            raise ValueError(
                "Source Code Analysis Agent response is missing "
                "required fields: "
                + ", ".join(missing_fields)
            )

        # --------------------------------------------------------------
        # Confidence validation.
        # --------------------------------------------------------------

        confidence = parsed["confidence"]

        if (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
        ):
            raise ValueError(
                "confidence must be between 0.0 and 1.0"
            )

        if not 0.0 <= float(confidence) <= 1.0:
            raise ValueError(
                "confidence must be between 0.0 and 1.0"
            )

        # --------------------------------------------------------------
        # Line number validation.
        # --------------------------------------------------------------

        if not isinstance(parsed["line_start"], int):
            raise ValueError(
                "line_start must be an integer"
            )

        if not isinstance(parsed["line_end"], int):
            raise ValueError(
                "line_end must be an integer"
            )

        # --------------------------------------------------------------
        # Normalize confidence.
        # --------------------------------------------------------------

        parsed["confidence"] = float(confidence)

        return parsed

    # ==================================================================
    # EMPTY INPUT FALLBACKS
    # ==================================================================

    def _empty_source_result(
        self,
        recent_commits_count: int,
    ) -> Dict[str, Any]:
        """Return result when no source snippets are available."""

        return {
            "agent": self.name,
            "status": "completed",

            "suspect_change": "",
            "file": "",
            "line_start": 0,
            "line_end": 0,
            "commit_sha": "",
            "explanation": (
                "No source-code snippets were available for analysis."
            ),
            "confidence": 0.0,

            "findings": [],
            "evidence": [],
            "hypotheses": [],

            "metadata": {
                "source_snippets_analyzed": 0,
                "recent_commits_analyzed": recent_commits_count,
            },
        }

    def _empty_commit_result(
        self,
        source_snippets_count: int,
    ) -> Dict[str, Any]:
        """Return result when no recent commits are available."""

        return {
            "agent": self.name,
            "status": "completed",

            "suspect_change": "",
            "file": "",
            "line_start": 0,
            "line_end": 0,
            "commit_sha": "",
            "explanation": (
                "Source-code snippets were available, but no recent "
                "commits were provided for change correlation."
            ),
            "confidence": 0.0,

            "findings": [],
            "evidence": [],
            "hypotheses": [],

            "metadata": {
                "source_snippets_analyzed": source_snippets_count,
                "recent_commits_analyzed": 0,
            },
        }

    # ==================================================================
    # EMPTY LLM RESPONSE FALLBACK
    # ==================================================================

    def _build_empty_llm_fallback(
        self,
        source_snippets: List[Dict[str, Any]],
        recent_commits: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Build a deterministic fallback when the LLM returns nothing.

        This fallback preserves source evidence so downstream Reasoning
        can still see that source-code evidence exists.

        Confidence remains 0.0 because the LLM did not validate the
        finding.
        """

        first_snippet = source_snippets[0]
        first_commit = recent_commits[0]

        # --------------------------------------------------------------
        # Determine suspicious change.
        # --------------------------------------------------------------

        suspect_change = (
            first_snippet.get("issue")
            or first_snippet.get("change")
            or first_snippet.get("description")
            or first_snippet.get("code")
            or "Potentially suspicious source-code change"
        )

        # --------------------------------------------------------------
        # File.
        # --------------------------------------------------------------

        file_name = (
            first_snippet.get("file")
            or first_snippet.get("path")
            or first_snippet.get("filename")
            or ""
        )

        # --------------------------------------------------------------
        # Line numbers.
        # --------------------------------------------------------------

        line_start = (
            first_snippet.get("line_start")
            or first_snippet.get("line")
            or first_snippet.get("start_line")
            or 0
        )

        line_end = (
            first_snippet.get("line_end")
            or first_snippet.get("end_line")
            or first_snippet.get("stop_line")
            or line_start
        )

        # --------------------------------------------------------------
        # Commit SHA.
        # --------------------------------------------------------------

        commit_sha = (
            first_commit.get("commit_sha")
            or first_commit.get("sha")
            or first_commit.get("hash")
            or ""
        )

        # --------------------------------------------------------------
        # Explanation.
        # --------------------------------------------------------------

        explanation = (
            first_snippet.get("issue")
            or first_snippet.get("change")
            or first_snippet.get("description")
            or (
                "The supplied source-code snippet is associated with "
                "a recent commit and requires investigation."
            )
        )

        finding = {
            "suspect_change": suspect_change,
            "file": file_name,
            "line_start": line_start,
            "line_end": line_end,
            "commit_sha": commit_sha,
            "explanation": explanation,
            "confidence": 0.0,
        }

        return {
            "agent": self.name,
            "status": "completed_with_fallback",

            "suspect_change": suspect_change,
            "file": file_name,
            "line_start": line_start,
            "line_end": line_end,
            "commit_sha": commit_sha,
            "explanation": explanation,
            "confidence": 0.0,

            "findings": [finding],

            "evidence": [
                {
                    "source_type": "source_code",
                    "source_id": file_name,
                    "field": "suspect_change",
                    "value": suspect_change,
                    "description": explanation,
                    "relevance": 0.0,
                    "agent": self.name,
                }
            ],

            "hypotheses": [],

            "metadata": {
                "source_snippets_analyzed": len(source_snippets),
                "recent_commits_analyzed": len(recent_commits),
                "fallback": True,
                "requires_human_review": True,
                "reason": "empty_llm_response",
            },
        }

    # ==================================================================
    # RESULT CONSTRUCTION
    # ==================================================================

    def _build_result(
        self,
        parsed: Dict[str, Any],
        source_snippets_count: int,
        commits_count: int,
    ) -> Dict[str, Any]:
        """Build the standardized source-code agent result."""

        finding = {
            "suspect_change": parsed["suspect_change"],
            "file": parsed["file"],
            "line_start": parsed["line_start"],
            "line_end": parsed["line_end"],
            "commit_sha": parsed["commit_sha"],
            "explanation": parsed["explanation"],
            "confidence": parsed["confidence"],
        }

        evidence = {
            "source_type": "source_code",
            "source_id": parsed["file"],
            "field": "suspect_change",
            "value": parsed["suspect_change"],
            "description": parsed["explanation"],
            "relevance": parsed["confidence"],
            "agent": self.name,
        }

        return {
            "agent": self.name,
            "status": "completed",

            # ----------------------------------------------------------
            # Top-level fields retained for compatibility with existing
            # tests and downstream consumers.
            # ----------------------------------------------------------

            "suspect_change": parsed["suspect_change"],
            "file": parsed["file"],
            "line_start": parsed["line_start"],
            "line_end": parsed["line_end"],
            "commit_sha": parsed["commit_sha"],
            "explanation": parsed["explanation"],
            "confidence": parsed["confidence"],

            # ----------------------------------------------------------
            # Structured output.
            # ----------------------------------------------------------

            "findings": [finding],
            "evidence": [evidence],
            "hypotheses": [],

            "metadata": {
                "source_snippets_analyzed": source_snippets_count,
                "recent_commits_analyzed": commits_count,
            },
        }

    # ==================================================================
    # MAIN AGENT EXECUTION
    # ==================================================================

    def run(
        self,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute source-code analysis.
        """

        raw_inputs = state.get(
            "raw_inputs",
            {},
        )

        # --------------------------------------------------------------
        # Validate raw_inputs.
        # --------------------------------------------------------------

        if not isinstance(raw_inputs, dict):
            raise ValueError(
                "raw_inputs must be a dictionary"
            )

        source_snippets = raw_inputs.get(
            "source_snippets",
            [],
        )

        recent_commits = raw_inputs.get(
            "recent_commits",
            [],
        )

        # Treat None as empty.
        if source_snippets is None:
            source_snippets = []

        if recent_commits is None:
            recent_commits = []

        # --------------------------------------------------------------
        # Validate source snippets.
        # --------------------------------------------------------------

        if not isinstance(source_snippets, list):
            raise ValueError(
                "source_snippets must be a list"
            )

        # --------------------------------------------------------------
        # Validate commits.
        # --------------------------------------------------------------

        if not isinstance(recent_commits, list):
            raise ValueError(
                "recent_commits must be a list"
            )

        # --------------------------------------------------------------
        # Empty source input.
        # --------------------------------------------------------------

        if not source_snippets:
            return self._empty_source_result(
                recent_commits_count=len(recent_commits)
            )

        # --------------------------------------------------------------
        # Empty commit input.
        # --------------------------------------------------------------

        if not recent_commits:
            return self._empty_commit_result(
                source_snippets_count=len(source_snippets)
            )

        # --------------------------------------------------------------
        # LLM validation.
        # --------------------------------------------------------------

        if self.llm is None:
            raise RuntimeError(
                "Source Code Analysis Agent requires an LLM callable"
            )

        if not callable(self.llm):
            raise RuntimeError(
                "Source Code Analysis Agent requires an LLM callable"
            )

        # --------------------------------------------------------------
        # Build prompt.
        # --------------------------------------------------------------

        prompt_text = self._build_prompt(
            source_snippets=source_snippets,
            recent_commits=recent_commits,
        )

        # --------------------------------------------------------------
        # LLM call.
        #
        # We retry ONLY when the response is empty.
        # We do not retry malformed JSON because the tests intentionally
        # expect JSONDecodeError / ValueError to propagate.
        # --------------------------------------------------------------

        response = self.llm(prompt_text)

        if hasattr(response, "content"):
            response = response.content

        if not isinstance(response, str):
            response = str(response)

        response = response.strip()

        # --------------------------------------------------------------
        # Empty response → one retry.
        # --------------------------------------------------------------

        if not response:
            logger.warning(
                "Source Code Analysis Agent received an empty "
                "LLM response. Retrying once."
            )

            response = self.llm(prompt_text)

            if hasattr(response, "content"):
                response = response.content

            if not isinstance(response, str):
                response = str(response)

            response = response.strip()

        # --------------------------------------------------------------
        # Still empty → deterministic fallback.
        # --------------------------------------------------------------

        if not response:
            logger.error(
                "Source Code Analysis Agent received an empty "
                "LLM response after retry. Using evidence-based fallback."
            )

            return self._build_empty_llm_fallback(
                source_snippets=source_snippets,
                recent_commits=recent_commits,
            )

        # --------------------------------------------------------------
        # Parse response.
        #
        # IMPORTANT:
        # Do not catch JSONDecodeError or ValueError here.
        # --------------------------------------------------------------

        parsed = self._parse_response(response)

        # --------------------------------------------------------------
        # Build final result.
        # --------------------------------------------------------------

        return self._build_result(
            parsed=parsed,
            source_snippets_count=len(source_snippets),
            commits_count=len(recent_commits),
        )