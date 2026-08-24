from fastapi import FastAPI, HTTPException
import os
import json
import ollama

app = FastAPI(title="Adaptive MAS RCA API")


# ==========================================
# CONFIGURATION
# ==========================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

LOG_DIR = os.path.join(BASE_DIR, "logs")

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "llama3"
)


# ==========================================
# HEALTH CHECK
# ==========================================

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "adaptive-mas-rca-backend"
    }


# ==========================================
# READ MICROSERVICE LOGS
# ==========================================

def read_logs():

    services = [
        "order-service",
        "payment-service",
        "inventory-service"
    ]

    events = []

    for service in services:

        log_file = os.path.join(
            LOG_DIR,
            f"{service}.jsonl"
        )

        if not os.path.exists(log_file):
            continue

        with open(
            log_file,
            "r",
            encoding="utf-8"
        ) as file:

            for line in file:

                line = line.strip()

                if not line:
                    continue

                try:
                    events.append(
                        json.loads(line)
                    )

                except json.JSONDecodeError:
                    continue

    return events


# ==========================================
# RCA ANALYSIS
# ==========================================

def analyze_with_llama(events):

    log_text = "\n".join(
        json.dumps(event)
        for event in events
    )

    prompt = f"""
You are an expert Root Cause Analysis assistant
for a distributed microservice system.

Analyze the following logs carefully.

IMPORTANT RCA RULES:

1. Identify the EARLIEST actual failure.
2. Do NOT automatically classify a timeout as a
   network failure.
3. If a log explicitly says "Simulated ... failure",
   treat that as the root cause.
4. Distinguish ROOT CAUSE from downstream symptoms.
5. A service failing because another service failed is
   a downstream effect.
6. Use timestamps and service names to reconstruct
   failure propagation.
7. Only claim a network problem when there is actual
   evidence of a network/connectivity failure.
8. Do not invent evidence.

Return these sections:

1. Incident
2. Failure Symptoms
3. Root Cause
4. Root Cause Service
5. Evidence
6. Failure Propagation
7. Confidence
8. Recommended Remediation

Logs:

{log_text}
"""

    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response["message"]["content"]


# ==========================================
# RCA API ENDPOINT
# ==========================================

@app.post("/api/rca/analyze")
def run_rca():

    events = read_logs()

    if not events:
        raise HTTPException(
            status_code=404,
            detail="No microservice logs found"
        )

    try:

        result = analyze_with_llama(events)

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"RCA analysis failed: {str(e)}"
        )

    # Save RCA result

    result_file = os.path.join(
        LOG_DIR,
        "rca_result.txt"
    )

    with open(
        result_file,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(result)

    return {
        "status": "success",
        "model": OLLAMA_MODEL,
        "events_analyzed": len(events),
        "root_cause_analysis": result
    }