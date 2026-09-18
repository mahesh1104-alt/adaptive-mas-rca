import json

import pytest

from app.agents.source_code_analysis_agent import (
    SourceCodeAnalysisAgent,
)

from app.source_preprocessing import (
    extract_code_units,
    parse_source,
    preprocess_source,
)


# ============================================================
# DELIBERATELY BUGGY SOURCE
# ============================================================

BUGGY_SOURCE = """
class InventoryService:
    \"\"\"Handles inventory operations.\"\"\"

    def update_stock(self, quantity):
        \"\"\"Update the inventory quantity.\"\"\"
        stock = 10

        # Deliberate bug:
        # quantity is subtracted twice.
        stock -= quantity
        stock -= quantity

        return stock

    def health_check(self):
        \"\"\"Check whether the service is healthy.\"\"\"
        return True


def unrelated_function():
    \"\"\"This function is unrelated to inventory updates.\"\"\"
    return "hello"
"""


# ============================================================
# RECENT COMMITS
# ============================================================

RECENT_COMMITS = [
    {
        "sha": "abc123",
        "message": "Update inventory stock handling",
        "author": "Mahesh",
        "date": "2026-09-15T10:00:00Z",
    },
    {
        "sha": "def456",
        "message": "Add inventory health check",
        "author": "Mahesh",
        "date": "2026-09-14T10:00:00Z",
    },
]


# ============================================================
# FAKE LLM
# ============================================================

def fake_llm(prompt):

    # Make sure source code was actually supplied
    assert "stock -= quantity" in prompt

    # Make sure commit history was supplied
    assert "Update inventory stock handling" in prompt

    return json.dumps(
        {
            "suspect_change": (
                "A duplicate stock subtraction was "
                "introduced in update_stock."
            ),
            "file": (
                "microservices/"
                "inventory-service/"
                "app.py"
            ),
            "line_start": 8,
            "line_end": 9,
            "commit_sha": "abc123",
            "explanation": (
                "The update_stock function subtracts "
                "quantity from stock twice. The recent "
                "inventory stock handling commit is "
                "therefore plausibly linked to the "
                "incorrect inventory calculation."
            ),
            "confidence": 0.96,
        }
    )


# ============================================================
# TEST 1
# DELIBERATE BUG DETECTION
# ============================================================

def test_source_code_agent_detects_deliberate_bug():

    # Parse source
    tree = parse_source(
        BUGGY_SOURCE
    )

    # Extract code units
    units = extract_code_units(
        tree
    )

    # Find update_stock
    update_stock = next(
        unit
        for unit in units
        if unit["name"] == "update_stock"
    )

    # Preprocess around the suspected fault
    snippets = preprocess_source(
        BUGGY_SOURCE,
        fault_line=update_stock["line"] + 2,
        context_lines=0,
    )

    # Ensure update_stock was selected
    update_stock_snippet = next(
        item
        for item in snippets
        if item["name"] == "update_stock"
    )

    assert (
        "stock -= quantity"
        in update_stock_snippet["code"]
    )

    # Create agent
    agent = SourceCodeAnalysisAgent(
        llm=fake_llm
    )

    # Build state
    state = {
        "trace_id": "source-code-001",
        "raw_inputs": {
            "source_snippets": snippets,
            "recent_commits": RECENT_COMMITS,
        },
    }

    # Run agent
    result = agent.run(
        state
    )

    # Basic structure
    assert "suspect_change" in result
    assert "file" in result
    assert "line_start" in result
    assert "line_end" in result
    assert "commit_sha" in result
    assert "explanation" in result
    assert "confidence" in result

    # Verify suspected bug
    assert (
        "duplicate"
        in result["suspect_change"].lower()
    )

    # Verify commit
    assert (
        result["commit_sha"]
        == "abc123"
    )

    # Verify confidence
    assert (
        result["confidence"]
        == 0.96
    )


# ============================================================
# TEST 2
# INVALID SOURCE INPUT
# ============================================================

def test_source_code_agent_requires_source_snippets():

    agent = SourceCodeAnalysisAgent(
        llm=fake_llm
    )

    state = {
        "trace_id": "source-code-002",
        "raw_inputs": {
            "source_snippets": "invalid",
            "recent_commits": RECENT_COMMITS,
        },
    }

    with pytest.raises(
        ValueError,
        match="source_snippets must be a list",
    ):
        agent.run(
            state
        )


# ============================================================
# TEST 3
# INVALID COMMIT INPUT
# ============================================================

def test_source_code_agent_requires_commits():

    agent = SourceCodeAnalysisAgent(
        llm=fake_llm
    )

    state = {
        "trace_id": "source-code-003",
        "raw_inputs": {
            "source_snippets": [
                {
                    "name": "update_stock",
                    "line": 3,
                    "end_line": 10,
                    "code": (
                        "stock -= quantity"
                    ),
                }
            ],
            "recent_commits": "invalid",
        },
    }

    with pytest.raises(
        ValueError,
        match="recent_commits must be a list",
    ):
        agent.run(
            state
        )


# ============================================================
# TEST 4
# EMPTY SOURCE
# ============================================================

def test_source_code_agent_handles_empty_source():

    agent = SourceCodeAnalysisAgent(
        llm=fake_llm
    )

    state = {
        "trace_id": "source-code-004",
        "raw_inputs": {
            "source_snippets": [],
            "recent_commits": RECENT_COMMITS,
        },
    }

    result = agent.run(
        state
    )

    assert (
        result["confidence"]
        == 0.0
    )

    assert (
        result["suspect_change"]
        == ""
    )

    assert (
        result["file"]
        == ""
    )

    assert (
        result["commit_sha"]
        == ""
    )


# ============================================================
# TEST 5
# EMPTY COMMITS
# ============================================================

def test_source_code_agent_handles_empty_commits():

    agent = SourceCodeAnalysisAgent(
        llm=fake_llm
    )

    state = {
        "trace_id": "source-code-005",
        "raw_inputs": {
            "source_snippets": [
                {
                    "name": "update_stock",
                    "line": 3,
                    "end_line": 10,
                    "code": (
                        "stock -= quantity"
                    ),
                }
            ],
            "recent_commits": [],
        },
    }

    result = agent.run(
        state
    )

    assert (
        result["confidence"]
        == 0.0
    )

    assert (
        result["commit_sha"]
        == ""
    )

    assert (
        result["suspect_change"]
        == ""
    )


# ============================================================
# TEST 6
# LLM IS REQUIRED
# ============================================================

def test_source_code_agent_requires_llm():

    agent = SourceCodeAnalysisAgent()

    state = {
        "trace_id": "source-code-006",
        "raw_inputs": {
            "source_snippets": [
                {
                    "name": "update_stock",
                    "line": 3,
                    "end_line": 10,
                    "code": (
                        "stock -= quantity"
                    ),
                }
            ],
            "recent_commits": RECENT_COMMITS,
        },
    }

    with pytest.raises(
        RuntimeError,
        match="requires an LLM callable",
    ):
        agent.run(
            state
        )


# ============================================================
# TEST 7
# INVALID JSON FROM LLM
# ============================================================

def test_source_code_agent_rejects_invalid_json():

    def invalid_llm(prompt):
        return "this is not valid JSON"

    agent = SourceCodeAnalysisAgent(
        llm=invalid_llm
    )

    state = {
        "trace_id": "source-code-007",
        "raw_inputs": {
            "source_snippets": [
                {
                    "name": "update_stock",
                    "line": 3,
                    "end_line": 10,
                    "code": (
                        "stock -= quantity"
                    ),
                }
            ],
            "recent_commits": RECENT_COMMITS,
        },
    }

    with pytest.raises(
        json.JSONDecodeError
    ):
        agent.run(
            state
        )


# ============================================================
# TEST 8
# INVALID CONFIDENCE
# ============================================================

def test_source_code_agent_rejects_invalid_confidence():

    def invalid_confidence_llm(prompt):

        return json.dumps(
            {
                "suspect_change": "test",
                "file": "app.py",
                "line_start": 1,
                "line_end": 2,
                "commit_sha": "abc123",
                "explanation": "test",
                "confidence": 1.5,
            }
        )

    agent = SourceCodeAnalysisAgent(
        llm=invalid_confidence_llm
    )

    state = {
        "trace_id": "source-code-008",
        "raw_inputs": {
            "source_snippets": [
                {
                    "name": "update_stock",
                    "line": 3,
                    "end_line": 10,
                    "code": (
                        "stock -= quantity"
                    ),
                }
            ],
            "recent_commits": RECENT_COMMITS,
        },
    }

    with pytest.raises(
        ValueError,
        match="confidence must be between",
    ):
        agent.run(
            state
        )