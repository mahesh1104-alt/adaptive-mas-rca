from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

from app.source_preprocessing import (
    extract_code_units,
    parse_source,
    preprocess_source,
    select_relevant_units,
    summarize_code_unit,
)


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


def test_parse_source():
    tree = parse_source(BUGGY_SOURCE)

    assert tree is not None


def test_extract_functions_and_classes():
    tree = parse_source(BUGGY_SOURCE)

    units = extract_code_units(tree)

    names = [
        unit["name"]
        for unit in units
    ]

    assert "InventoryService" in names
    assert "update_stock" in names
    assert "health_check" in names
    assert "unrelated_function" in names


def test_select_relevant_units():
    tree = parse_source(BUGGY_SOURCE)

    units = extract_code_units(tree)

    update_stock = next(
        unit
        for unit in units
        if unit["name"] == "update_stock"
    )

    relevant = select_relevant_units(
        units,
        fault_line=update_stock["line"] + 2,
        context_lines=0,
    )

    names = [
        unit["name"]
        for unit in relevant
    ]

    assert "update_stock" in names


def test_docstring_summary():
    tree = parse_source(BUGGY_SOURCE)

    units = extract_code_units(tree)

    update_stock = next(
        unit
        for unit in units
        if unit["name"] == "update_stock"
    )

    summary = summarize_code_unit(
        update_stock
    )

    assert summary == "Update the inventory quantity."


def test_complete_source_preprocessing():
    tree = parse_source(BUGGY_SOURCE)

    units = extract_code_units(tree)

    update_stock = next(
        unit
        for unit in units
        if unit["name"] == "update_stock"
    )

    results = preprocess_source(
        BUGGY_SOURCE,
        fault_line=update_stock["line"] + 2,
        context_lines=0,
    )

    names = [
        result["name"]
        for result in results
    ]

    assert "update_stock" in names

    result = next(
        result
        for result in results
        if result["name"] == "update_stock"
    )

    assert (
        result["summary"]
        == "Update the inventory quantity."
    )

    assert "stock -= quantity" in result["code"]

def test_preprocess_repository_file_endpoint():
    client = TestClient(app)

    file_data = {
        "name": "app.py",
        "path": "microservices/inventory-service/app.py",
        "size": len(BUGGY_SOURCE),
        "sha": "test-sha",
        "html_url": "https://github.com/test/app.py",
        "content": BUGGY_SOURCE,
    }

    with patch(
        "app.main.get_service_repository"
    ) as mock_repository:

        mock_repository.return_value = {
            "repository": "test-owner/test-repo",
            "path": "microservices/inventory-service",
        }

        with patch(
            "app.main.fetch_source_file"
        ) as mock_fetch:

            mock_fetch.return_value = file_data

            response = client.get(
                "/api/repository/inventory-service/preprocess",
                params={
                    "path": (
                        "microservices/inventory-service/"
                        "app.py"
                    ),
                    "fault_line": 7,
                    "context_lines": 0,
                },
            )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"
    assert data["service"] == "inventory-service"
    assert data["file"]["name"] == "app.py"

    names = [
        unit["name"]
        for unit in data["units"]
    ]

    assert "update_stock" in names

    update_stock = next(
        unit
        for unit in data["units"]
        if unit["name"] == "update_stock"
    )

    assert (
        update_stock["summary"]
        == "Update the inventory quantity."
    )

    assert "stock -= quantity" in update_stock["code"]

    mock_fetch.assert_called_once()