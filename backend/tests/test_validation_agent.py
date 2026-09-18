from app.agents.validation_agent import ValidationAgent


def make_state(
    root_cause="Database connection pool exhausted",
    confidence=0.90,
    evidence=None,
):
    if evidence is None:
        evidence = [
            {
                "source_type": "log",
                "description": "Database connection pool exhausted",
            }
        ]

    return {
        "raw_inputs": {
            "logs": [
                {
                    "message": "Database connection pool exhausted"
                }
            ]
        },
        "agent_outputs": {
            "reasoning_agent": {
                "agent": "reasoning_agent",
                "status": "completed",
                "confidence": confidence,
                "metadata": {
                    "final_report": {
                        "root_cause": root_cause,
                        "confidence": confidence,
                        "supporting_evidence": evidence,
                    }
                },
            }
        },
    }


def test_valid_rca_passes_validation():
    agent = ValidationAgent()

    result = agent.run(make_state())

    assert result.status == "completed"
    assert result.metadata["validated"] is True
    assert result.metadata["requires_human_review"] is False


def test_missing_root_cause_requires_review():
    agent = ValidationAgent()

    result = agent.run(
        make_state(root_cause="")
    )

    assert result.metadata["validated"] is False
    assert result.metadata["requires_human_review"] is True


def test_missing_evidence_requires_review():
    agent = ValidationAgent()

    result = agent.run(
        make_state(evidence=[])
    )

    assert result.metadata["validated"] is False
    assert result.metadata["requires_human_review"] is True


def test_low_confidence_requires_review():
    agent = ValidationAgent()

    result = agent.run(
        make_state(confidence=0.40)
    )

    assert result.metadata["validated"] is False
    assert result.metadata["requires_human_review"] is True


def test_symptom_as_root_cause_requires_review():
    agent = ValidationAgent()

    result = agent.run(
        make_state(
            root_cause="Request latency exceededthreshold"
        )
    )

    assert result.metadata["validated"] is False
    assert result.metadata["requires_human_review"] is True


def test_strong_evidence_produces_numeric_validation_confidence():
    agent = ValidationAgent()

    result = agent.run(make_state())

    validation_confidence = result.metadata["validation_confidence"]

    assert isinstance(validation_confidence, float)
    assert 0.0 <= validation_confidence <= 1.0
    assert validation_confidence >= 0.70


def test_weak_evidence_requires_human_review():
    agent = ValidationAgent()

    result = agent.run(
        make_state(
            root_cause="Database connection pool exhausted",
            confidence=0.90,
            evidence=[
                {
                    "source_type": "metric",
                    "description": "Unrelated CPU anomaly",
                }
            ],
        )
    )

    assert result.metadata["validated"] is False
    assert result.metadata["requires_human_review"] is True
    assert result.metadata["evidence_overlap"] < 1.0


def test_evidence_overlap_is_computed():
    agent = ValidationAgent()

    evidence = [
        {
            "source_type": "log",
            "description": "Database connection pool exhausted",
        },
        {
            "source_type": "metric",
            "description": "Unrelated CPU anomaly",
        },
    ]

    result = agent.run(
        make_state(evidence=evidence)
    )

    assert "evidence_overlap" in result.metadata
    assert 0.0 <= result.metadata["evidence_overlap"] <= 1.0
