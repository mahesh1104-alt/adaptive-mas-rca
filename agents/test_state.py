from state import AgentState


state: AgentState = {
    "raw_inputs": {
        "incident_id": "INC-001",
        "description": "Backend unable to connect to PostgreSQL",
        "severity": "HIGH"
    },

    "agent_outputs": {},

    "confidence": {},

    "final_report": None,

    "trace_id": "TRACE-001"
}


print("========================================")
print("ADAPTIVE MAS-RCA AGENT STATE")
print("========================================")

print("\nRaw Inputs:")
print(state["raw_inputs"])

print("\nAgent Outputs:")
print(state["agent_outputs"])

print("\nConfidence:")
print(state["confidence"])

print("\nFinal Report:")
print(state["final_report"])

print("\nTrace ID:")
print(state["trace_id"])

print("\nState schema test successful!")