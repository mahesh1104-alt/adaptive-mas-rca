# Subtask 14: LLM Provider Selection

## Selected LLM Provider

The selected LLM provider for the Adaptive MAS-RCA
system is Ollama running the Llama 3 model locally.

## Provider Details

| Parameter | Value |
|---|---|
| Provider | Ollama |
| Model | Llama 3 |
| Deployment | Local |
| API Endpoint | http://localhost:11434 |
| API Key | Not required |
| Integration | Python Ollama Client |

## Provider Selection Rationale

Ollama with Llama 3 was selected for the initial
implementation of the Adaptive MAS-RCA system because
the model can run locally without requiring an external
API key.

The main advantages are:

- Local execution
- No per-request API cost
- No external API key required
- Better control over project data
- Easy Python integration
- Easy integration with LangGraph
- Suitable for development and testing

## RCA Prompt Test

A sample PostgreSQL connection failure incident was
used to evaluate the selected LLM.

### Incident

Incident ID: INC-001

Title: PostgreSQL connection failure

Severity: HIGH

Description:

Backend unable to connect to PostgreSQL.

### Sample Evidence

- Backend unable to connect to PostgreSQL
- Connection refused at port 5432
- Database connection retry failed
- Maximum connection retries exceeded

## LLM Output

The Llama 3 model successfully produced:

1. Incident identification
2. Symptoms
3. Probable root cause
4. Supporting evidence
5. Confidence assessment
6. Recommended remediation

The model identified possible causes including network
connectivity, firewall configuration, database
configuration, and authentication/authorization issues.

## Performance Test

The Python Ollama client was used to measure response
latency.

### Measured Latency

15.87 seconds

The latency includes the time required for the local
Llama 3 model to process the RCA prompt and generate
the response.

## Final Decision

Ollama + Llama 3 has been selected as the LLM provider
for the Adaptive MAS-RCA prototype.

The provider is successfully installed, accessible
through the local Ollama API, and tested using a sample
RCA scenario.

## Integration Status

- Ollama installed: Complete
- Llama 3 model available: Complete
- Python integration: Complete
- RCA prompt test: Complete
- Latency measurement: Complete
- Provider documentation: Complete

## Future Consideration

For production deployment, other providers such as
OpenAI GPT models or Llama models served through
vLLM can be evaluated based on latency, cost,
context-window requirements, accuracy, privacy, and
infrastructure requirements.