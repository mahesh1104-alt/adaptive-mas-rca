import math

import ollama


RAG_CONTEXT_TOKEN_BUDGET = 8000
OLLAMA_MODEL = "llama3"


SYSTEM_PROMPT = """
You are an incident root-cause analysis assistant.

Use only the evidence provided in the prompt.
Do not invent logs, metrics, incidents, root causes, or relationships.
Distinguish observed evidence from historical evidence.
Cite supporting historical evidence using the supplied citation markers.

Provide:
1. Most likely root cause
2. Supporting evidence
3. Affected service
4. Recommended next investigation steps

If the evidence is insufficient, explicitly say so.
""".strip()


def estimate_tokens(text: str) -> int:
    """
    Estimate LLM token usage without requiring a tokenizer dependency.

    The estimate uses approximately four characters per token and rounds up.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    if not text:
        return 0

    return max(1, math.ceil(len(text) / 4))


def _format_logs(logs: list[dict]) -> str:
    if not logs:
        return "No current logs available."

    lines = []

    for index, log in enumerate(logs, start=1):
        level = str(log.get("level", "UNKNOWN"))
        template = str(
            log.get("template")
            or log.get("message")
            or ""
        )
        timestamp = str(log.get("timestamp", ""))

        timestamp_text = (
            f" [{timestamp}]"
            if timestamp
            else ""
        )

        lines.append(
            f"- Log {index}{timestamp_text} "
            f"[{level}]: {template}"
        )

    return "\n".join(lines)


def _format_metrics(metrics: list[dict]) -> str:
    if not metrics:
        return "No current metrics available."

    lines = []

    for index, metric in enumerate(metrics, start=1):
        name = str(metric.get("name", "unknown_metric"))
        value = str(metric.get("value", ""))
        unit = str(metric.get("unit", ""))
        service = str(metric.get("service", ""))

        service_text = (
            f" service={service}"
            if service
            else ""
        )

        unit_text = f" {unit}" if unit else ""

        lines.append(
            f"- Metric {index}: {name}={value}{unit_text}"
            f"{service_text}"
        )

    return "\n".join(lines)


def _format_graph_evidence(
    graph_evidence: list[dict],
    incident_id: str,
) -> str:
    if not graph_evidence:
        return "No graph evidence available."

    lines = []

    for evidence in graph_evidence:
        service = str(evidence.get("service", ""))
        root_cause = str(evidence.get("root_cause", ""))
        hop_count = evidence.get("hop_count", 0)

        lines.append(
            f"- [{incident_id}] "
            f"Service: {service}; "
            f"Root cause: {root_cause}; "
            f"Graph hops: {hop_count}"
        )

    return "\n".join(lines)


def _format_historical_evidence(
    evidence: dict,
    citation_number: int,
) -> str:
    incident_id = str(
        evidence.get("incident_id", "UNKNOWN")
    )
    service = str(evidence.get("service", ""))
    title = str(evidence.get("title", ""))
    document = str(evidence.get("document", ""))
    vector_score = evidence.get("vector_score", 0.0)
    graph_score = evidence.get("graph_score", 0.0)

    citation = f"[Incident #{citation_number}: {incident_id}]"

    lines = [
        f"{citation}",
        f"Incident: {incident_id}",
        f"Service: {service}",
        f"Failure type: {title}",
        f"Vector relevance: {vector_score:.4f}",
        f"Graph relevance: {graph_score:.4f}",
    ]

    if document:
        lines.append(f"Historical details:\n{document}")

    graph_text = _format_graph_evidence(
        evidence.get("graph_evidence", []),
        incident_id,
    )

    lines.append(f"Graph facts:\n{graph_text}")

    return "\n".join(lines)


def _evidence_block(
    evidence: dict,
    citation_number: int,
) -> str:
    return _format_historical_evidence(
        evidence=evidence,
        citation_number=citation_number,
    )


def _build_static_prompt(
    query: str,
    logs: list[dict],
    metrics: list[dict],
) -> str:
    return f"""
{SYSTEM_PROMPT}

CURRENT INCIDENT

Incident query:
{query}

CURRENT LOGS
{_format_logs(logs)}

CURRENT METRICS
{_format_metrics(metrics)}

HISTORICAL AND GRAPH EVIDENCE
""".strip()


def _select_evidence_within_budget(
    query: str,
    logs: list[dict],
    metrics: list[dict],
    retrieved_evidence: list[dict],
    token_budget: int,
) -> list[tuple[int, dict, str]]:
    static_prompt = _build_static_prompt(
        query=query,
        logs=logs,
        metrics=metrics,
    )

    base_tokens = estimate_tokens(static_prompt)

    if base_tokens >= token_budget:
        return []

    remaining_tokens = token_budget - base_tokens

    selected = []

    ranked_evidence = sorted(
        retrieved_evidence,
        key=lambda item: item.get("relevance_score", 0.0),
        reverse=True,
    )

    for citation_number, evidence in enumerate(
        ranked_evidence,
        start=1,
    ):
        block = _evidence_block(
            evidence=evidence,
            citation_number=citation_number,
        )

        block_tokens = estimate_tokens(block)

        if block_tokens <= remaining_tokens:
            selected.append(
                (
                    citation_number,
                    evidence,
                    block,
                )
            )
            remaining_tokens -= block_tokens

    return selected


def format_rag_prompt(
    query: str,
    logs: list[dict] | None = None,
    metrics: list[dict] | None = None,
    retrieved_evidence: list[dict] | None = None,
    token_budget: int = RAG_CONTEXT_TOKEN_BUDGET,
) -> str:
    """
    Build a token-bounded RAG prompt from current and retrieved evidence.

    Retrieved evidence is ordered by relevance and the lowest-relevance
    items are excluded first when the token budget is exceeded.
    """
    if not isinstance(query, str):
        raise TypeError("query must be a string")

    if not query.strip():
        raise ValueError("query cannot be empty")

    if token_budget < 1:
        raise ValueError("token_budget must be at least 1")

    logs = logs or []
    metrics = metrics or []
    retrieved_evidence = retrieved_evidence or []

    selected = _select_evidence_within_budget(
        query=query,
        logs=logs,
        metrics=metrics,
        retrieved_evidence=retrieved_evidence,
        token_budget=token_budget,
    )

    static_prompt = _build_static_prompt(
        query=query,
        logs=logs,
        metrics=metrics,
    )

    if selected:
        evidence_text = "\n\n".join(
            block
            for _, _, block in selected
        )
    else:
        evidence_text = "No historical evidence fits within the token budget."

    prompt = f"""
{static_prompt}

{evidence_text}

ANALYSIS INSTRUCTIONS

Analyze the current incident using the evidence above.

Rank the possible causes by confidence.
Use citation markers such as [Incident #1: INC-005] when referring to historical evidence.
Do not treat historical evidence as proof that the current incident has the same root cause.
Explain which current logs and metrics support the conclusion.

Return a concise root-cause analysis.
""".strip()

    return prompt


def generate_rag_response(prompt: str) -> str:
    """
    Send a formatted RAG prompt to the project's selected LLM.
    """
    if not isinstance(prompt, str):
        raise TypeError("prompt must be a string")

    if not prompt.strip():
        raise ValueError("prompt cannot be empty")

    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    return response["message"]["content"]