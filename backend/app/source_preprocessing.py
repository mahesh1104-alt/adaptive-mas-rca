"""
Source code preprocessing module for Adaptive MAS RCA.

Responsibilities:
- Parse Python source code using the AST module.
- Extract functions, async functions, and classes.
- Identify code units near a suspected fault location.
- Extract docstrings as lightweight summaries.
- Return relevant source snippets instead of entire files.

The module is intentionally independent from FastAPI so that it can
be tested directly and reused by the RCA pipeline.
"""

from __future__ import annotations

import ast
from typing import Any, Dict, List, Optional


# ============================================================
# TYPE ALIASES
# ============================================================

CodeUnit = Dict[str, Any]


# ============================================================
# SOURCE PARSING
# ============================================================

def parse_source(source: str) -> ast.AST:
    """
    Parse Python source code into an abstract syntax tree.

    Args:
        source: Python source code as a string.

    Returns:
        Parsed Python AST.

    Raises:
        SyntaxError: If the source contains invalid Python syntax.
    """

    if not isinstance(source, str):
        raise TypeError("source must be a string")

    return ast.parse(source)


# ============================================================
# CODE UNIT EXTRACTION
# ============================================================

def extract_code_units(tree: ast.AST) -> List[CodeUnit]:
    """
    Extract functions and classes from a Python AST.

    Functions, async functions, and classes are treated as
    potentially relevant source-code units.

    Returns:
        A list containing metadata about each code unit.
    """

    units: List[CodeUnit] = []

    for node in ast.walk(tree):

        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        ):
            continue

        units.append(
            {
                "type": type(node).__name__,
                "name": node.name,
                "line": node.lineno,
                "end_line": getattr(
                    node,
                    "end_lineno",
                    node.lineno,
                ),
                "docstring": ast.get_docstring(node),
                "node": node,
            }
        )

    units.sort(key=lambda unit: unit["line"])

    return units


# ============================================================
# CODE SUMMARY
# ============================================================

def summarize_code_unit(unit: CodeUnit) -> str:
    """
    Generate a lightweight summary for a code unit.

    The docstring is preferred when available. If no docstring
    exists, a fallback description based on the unit type/name
    is returned.
    """

    docstring = unit.get("docstring")

    if docstring:
        return str(docstring).strip()

    unit_type = unit.get("type", "CodeUnit")
    name = unit.get("name", "unknown")

    if unit_type == "ClassDef":
        return f"Class {name}."

    if unit_type in {
        "FunctionDef",
        "AsyncFunctionDef",
    }:
        return f"Function {name}."

    return f"{unit_type} {name}."


# ============================================================
# SOURCE SNIPPET EXTRACTION
# ============================================================

def extract_source_snippet(
    source: str,
    unit: CodeUnit,
) -> str:
    """
    Extract the source-code snippet corresponding to a code unit.
    """

    lines = source.splitlines()

    start_line = int(unit["line"]) - 1
    end_line = int(unit["end_line"])

    return "\n".join(
        lines[start_line:end_line]
    )


# ============================================================
# FAULT-LOCATION FILTERING
# ============================================================

def select_relevant_units(
    units: List[CodeUnit],
    fault_line: Optional[int] = None,
    context_lines: int = 20,
) -> List[CodeUnit]:
    """
    Select code units relevant to a suspected fault location.

    A code unit is considered relevant when:

    1. The fault line falls inside the unit, or
    2. The unit starts near the fault line, or
    3. The unit ends near the fault line.

    If no fault line is supplied, all extracted units are returned.
    """

    if context_lines < 0:
        raise ValueError(
            "context_lines must be greater than or equal to zero"
        )

    if fault_line is None:
        return list(units)

    if fault_line <= 0:
        raise ValueError(
            "fault_line must be greater than zero"
        )

    relevant: List[CodeUnit] = []

    for unit in units:

        start_line = int(unit["line"])
        end_line = int(unit["end_line"])

        inside_unit = (
            start_line <= fault_line <= end_line
        )

        near_start = (
            abs(start_line - fault_line)
            <= context_lines
        )

        near_end = (
            abs(end_line - fault_line)
            <= context_lines
        )

        if inside_unit or near_start or near_end:
            relevant.append(unit)

    return relevant


# ============================================================
# COMPLETE SOURCE PREPROCESSING
# ============================================================

def preprocess_source(
    source: str,
    fault_line: Optional[int] = None,
    context_lines: int = 20,
) -> List[CodeUnit]:
    """
    Complete source-code preprocessing pipeline.

    Steps:

    1. Parse Python source using AST.
    2. Extract functions and classes.
    3. Select units near the suspected fault location.
    4. Extract source snippets.
    5. Generate summaries.

    Returns:
        A list of relevant summarized code units.
    """

    tree = parse_source(source)

    units = extract_code_units(tree)

    relevant_units = select_relevant_units(
        units,
        fault_line=fault_line,
        context_lines=context_lines,
    )

    results: List[CodeUnit] = []

    for unit in relevant_units:

        result = {
            "type": unit["type"],
            "name": unit["name"],
            "line": unit["line"],
            "end_line": unit["end_line"],
            "summary": summarize_code_unit(unit),
            "code": extract_source_snippet(
                source,
                unit,
            ),
        }

        results.append(result)

    return results