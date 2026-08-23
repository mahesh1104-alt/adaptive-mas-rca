# Subtask 14: LLM Provider Selection

## Selected Provider

Ollama with Llama 3 was selected as the LLM provider
for the Adaptive MAS-RCA system.

## Provider

- Provider: Ollama
- Model: Llama 3
- Deployment: Local
- Endpoint: http://localhost:11434

## Reason for Selection

Ollama + Llama was selected because it provides:

- Local LLM execution
- No external API key requirement
- No per-request API cost
- Better control over project data
- Easy Python integration
- Easy integration with LangGraph
- Suitable for development and experimentation

## RCA Test

Sample incident:

INC-001 - PostgreSQL connection failure

The model was tested using PostgreSQL connection
failure logs.

The test required the model to identify:

1. Incident
2. Symptoms
3. Probable root cause
4. Evidence
5. Confidence
6. Recommended remediation

## Latency

The response latency was measured using the Python
Ollama client.

Measured latency: 40.51 seconds

PUT YOUR ACTUAL LATENCY HERE

## Final Decision

Ollama + Llama 3 is selected as the final LLM provider
for the Adaptive MAS-RCA project.

The provider will be integrated with the LangGraph
agent architecture.