import time
import ollama

prompt = """
You are an RCA assistant for an Adaptive Multi-Agent
Root Cause Analysis system.

Analyze the following incident.

Incident ID: INC-001
Title: PostgreSQL connection failure
Severity: HIGH

Description:
Backend unable to connect to PostgreSQL.

Logs:
2026-08-19 10:00:01 ERROR Backend
Unable to connect to PostgreSQL

2026-08-19 10:00:02 ERROR
Connection refused at port 5432

2026-08-19 10:00:05 WARN
Database connection retry failed

2026-08-19 10:00:10 ERROR
Maximum connection retries exceeded

Provide:
1. Incident
2. Symptoms
3. Root cause
4. Evidence
5. Confidence
6. Recommended remediation
"""

print("===================================")
print("OLLAMA + LLAMA RCA TEST")
print("===================================")

start_time = time.time()

response = ollama.chat(
    model="llama3",
    messages=[
        {
            "role": "user",
            "content": prompt
        }
    ]
)

end_time = time.time()

latency = end_time - start_time

print("\nRCA RESPONSE:")
print(response["message"]["content"])

print("\n===================================")
print(f"Response latency: {latency:.2f} seconds")
print("===================================")