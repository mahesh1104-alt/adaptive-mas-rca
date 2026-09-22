from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AgentOutput, Feedback


# Specialized agents whose historical feedback should influence
# Reasoning Agent aggregation.
SPECIALIZED_AGENTS = (
    "log_analysis_agent",
    "metrics_analysis_agent",
    "source_code_analysis_agent",
    "trace_analysis_agent",
)

# Neutral prior used when an agent has little or no feedback.
DEFAULT_TRUST = 0.5

# Maximum number of recent feedback outcomes considered per agent.
DEFAULT_WINDOW_SIZE = 20


def calculate_agent_trust_weights(
    db: Session,
    window_size: int = DEFAULT_WINDOW_SIZE,
) -> dict[str, float]:
    """
    Calculate rolling trust weights from engineer feedback.

    Trust is calculated independently for each specialized agent.

    A Laplace-smoothed accuracy is used:

        trust = (correct + 1) / (total + 2)

    This prevents an agent with only one feedback record from
    immediately receiving an extreme weight.

    The resulting weights are normalized around 1.0 so that:

        1.0 = neutral influence
        > 1.0 = historically stronger influence
        < 1.0 = historically weaker influence
    """

    if window_size <= 0:
        raise ValueError("window_size must be greater than zero")

    # Start every specialized agent with a neutral trust value.
    trust_scores: dict[str, float] = {
        agent_name: DEFAULT_TRUST
        for agent_name in SPECIALIZED_AGENTS
    }

    # Retrieve feedback joined with the agent output it evaluates.
    feedback_rows = (
        db.query(
            AgentOutput.agent_type,
            AgentOutput.agent_name,
            Feedback.is_correct,
            Feedback.created_at,
        )
        .join(
            Feedback,
            Feedback.output_id == AgentOutput.output_id,
        )
        .filter(
            Feedback.is_correct.isnot(None),
            AgentOutput.agent_type.in_(SPECIALIZED_AGENTS),
        )
        .order_by(Feedback.created_at.desc())
        .all()
    )

    # Keep only the most recent N feedback records per agent.
    recent_feedback: dict[str, list[bool]] = defaultdict(list)

    for row in feedback_rows:
        agent_type = row.agent_type or row.agent_name

        if agent_type not in SPECIALIZED_AGENTS:
            continue

        if len(recent_feedback[agent_type]) >= window_size:
            continue

        recent_feedback[agent_type].append(
            bool(row.is_correct)
        )

    # Calculate smoothed historical accuracy.
    for agent_name in SPECIALIZED_AGENTS:
        outcomes = recent_feedback.get(agent_name, [])

        if not outcomes:
            trust_scores[agent_name] = DEFAULT_TRUST
            continue

        correct = sum(outcomes)
        total = len(outcomes)

        trust_scores[agent_name] = (
            (correct + 1.0) / (total + 2.0)
        )

    # Normalize around a mean weight of 1.0.
    average_trust = sum(trust_scores.values()) / len(
        trust_scores
    )

    if average_trust <= 0.0:
        return {
            agent_name: 1.0
            for agent_name in SPECIALIZED_AGENTS
        }

    normalized_weights = {
        agent_name: round(
            trust / average_trust,
            4,
        )
        for agent_name, trust in trust_scores.items()
    }

    return normalized_weights


def get_agent_trust_details(
    db: Session,
    window_size: int = DEFAULT_WINDOW_SIZE,
) -> dict[str, dict[str, Any]]:
    """
    Return trust statistics for debugging, evaluation and testing.

    This exposes:
    - recent feedback count
    - correct count
    - rolling accuracy
    - normalized trust weight
    """

    if window_size <= 0:
        raise ValueError("window_size must be greater than zero")

    feedback_rows = (
        db.query(
            AgentOutput.agent_type,
            AgentOutput.agent_name,
            Feedback.is_correct,
            Feedback.created_at,
        )
        .join(
            Feedback,
            Feedback.output_id == AgentOutput.output_id,
        )
        .filter(
            Feedback.is_correct.isnot(None),
            AgentOutput.agent_type.in_(SPECIALIZED_AGENTS),
        )
        .order_by(Feedback.created_at.desc())
        .all()
    )

    recent_feedback: dict[str, list[bool]] = defaultdict(list)

    for row in feedback_rows:
        agent_type = row.agent_type or row.agent_name

        if agent_type not in SPECIALIZED_AGENTS:
            continue

        if len(recent_feedback[agent_type]) >= window_size:
            continue

        recent_feedback[agent_type].append(
            bool(row.is_correct)
        )

    weights = calculate_agent_trust_weights(
        db,
        window_size=window_size,
    )

    details: dict[str, dict[str, Any]] = {}

    for agent_name in SPECIALIZED_AGENTS:
        outcomes = recent_feedback.get(agent_name, [])
        correct = sum(outcomes)
        total = len(outcomes)

        accuracy = (
            correct / total
            if total > 0
            else DEFAULT_TRUST
        )

        details[agent_name] = {
            "feedback_count": total,
            "correct_count": correct,
            "incorrect_count": total - correct,
            "rolling_accuracy": round(
                accuracy,
                4,
            ),
            "trust_weight": weights[agent_name],
        }

    return details
