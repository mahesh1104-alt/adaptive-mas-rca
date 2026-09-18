from app.ollama_adapter import ollama_llm


def test_ollama_llm_returns_response():
    response = ollama_llm(
        "Reply with exactly: INTEGRATION TEST PASSED"
    )

    assert isinstance(response, str)
    assert "INTEGRATION TEST PASSED" in response
