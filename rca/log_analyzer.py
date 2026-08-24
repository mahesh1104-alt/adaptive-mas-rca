import json
import os
import ollama


LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "logs"
)

MODEL = "llama3"


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
                    pass

    return events


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

1. Identify the EARLIEST actual failure in the event chain.
2. Do NOT automatically classify a timeout as a network failure.
3. If a log explicitly says "Simulated ... failure",
   treat that as the root cause.
4. Distinguish the ROOT CAUSE from downstream symptoms.
5. A service returning an error because another service
   failed is a DOWNSTREAM EFFECT, not necessarily the
   root cause.
6. Use timestamps and service names to reconstruct the
   failure propagation.
7. Only claim a network problem when the logs contain
   actual evidence of a network/connectivity failure.
8. Do not invent evidence that is not present in the logs.

Provide the result using exactly these sections:

1. Incident
2. Failure Symptoms
3. Root Cause
4. Root Cause Service
5. Evidence
6. Failure Propagation
7. Confidence
8. Recommended Remediation

For Evidence, quote or closely reference the actual
log messages that support the conclusion.

For Failure Propagation, explain the chain such as:

Order Service
    ↓
Payment Service
    ↓
Inventory Service
    ↓
Root Failure

Logs:

{log_text}
"""

    response = ollama.chat(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response["message"]["content"]


def main():

    print("=" * 50)
    print("ADAPTIVE MAS RCA - LOG ANALYZER")
    print("=" * 50)

    events = read_logs()

    print(f"\nLoaded {len(events)} log events.")

    if not events:
        print("No logs found.")
        return

    print("\nSending logs to Ollama...")

    result = analyze_with_llama(events)

    print("\n" + "=" * 50)
    print("ROOT CAUSE ANALYSIS")
    print("=" * 50)

    print(result)

    output_file = os.path.join(
        LOG_DIR,
        "rca_result.txt"
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(result)

    print("\nRCA saved to:")
    print(output_file)


if __name__ == "__main__":
    main()