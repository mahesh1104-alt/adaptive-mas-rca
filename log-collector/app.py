from flask import Flask, jsonify, request
import os
import json
from datetime import datetime

app = Flask(__name__)

LOG_DIR = os.getenv("LOG_DIR", "/logs")

SERVICES = {
    "order-service": "order-service.jsonl",
    "payment-service": "payment-service.jsonl",
    "inventory-service": "inventory-service.jsonl"
}


def read_logs():
    events = []

    for service, filename in SERVICES.items():
        filepath = os.path.join(LOG_DIR, filename)

        if not os.path.exists(filepath):
            continue

        with open(filepath, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()

                if not line:
                    continue

                try:
                    event = json.loads(line)

                    if "service" not in event:
                        event["service"] = service

                    events.append(event)

                except json.JSONDecodeError:
                    continue

    events.sort(
        key=lambda event: event.get("timestamp", "")
    )

    return events


@app.route("/health")
def health():
    return jsonify({
        "service": "log-collector",
        "status": "healthy"
    })


@app.route("/logs")
def get_logs():

    events = read_logs()

    service = request.args.get("service")
    start = request.args.get("start")
    end = request.args.get("end")

    if service:
        events = [
            event for event in events
            if event.get("service") == service
        ]

    if start:
        events = [
            event for event in events
            if event.get("timestamp", "") >= start
        ]

    if end:
        events = [
            event for event in events
            if event.get("timestamp", "") <= end
        ]

    return jsonify({
        "count": len(events),
        "logs": events
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8010
    )