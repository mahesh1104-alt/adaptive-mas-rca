from flask import Flask, jsonify
from prometheus_flask_exporter import PrometheusMetrics
import requests
import os
import logging
import json
from datetime import datetime, timezone

app = Flask(__name__)
metrics = PrometheusMetrics(app)
PAYMENT_URL = os.getenv(
    "PAYMENT_URL",
    "http://localhost:8002"
)


# ==========================================
# JSON LOGGER
# ==========================================

# Create the logs directory inside the container
os.makedirs("/logs", exist_ok=True)


class JSONFormatter(logging.Formatter):

    def format(self, record):
        log = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "order-service",
            "level": record.levelname,
            "message": record.getMessage()
        }

        return json.dumps(log)


logger = logging.getLogger("order-service")
logger.setLevel(logging.INFO)

# Prevent duplicate handlers
if not logger.handlers:

    handler = logging.FileHandler(
        "/logs/order-service.jsonl"
    )

    handler.setFormatter(JSONFormatter())

    logger.addHandler(handler)


# ==========================================
# HEALTH CHECK
# ==========================================

@app.route("/health")
def health():

    logger.info("Health check requested")

    return jsonify({
        "service": "order-service",
        "status": "healthy"
    })


# ==========================================
# CREATE ORDER
# ==========================================

@app.route("/order/<order_id>")
def create_order(order_id):

    logger.info(
        f"Creating order {order_id}"
    )

    try:

        response = requests.get(
            f"{PAYMENT_URL}/pay/{order_id}",
            timeout=5
        )

        logger.info(
            f"Payment service returned status "
            f"{response.status_code}"
        )

        return jsonify({
            "order_id": order_id,
            "payment_status": response.json()
        }), response.status_code

    except Exception as e:

        logger.error(
            f"Payment service failed: {str(e)}"
        )

        return jsonify({
            "order_id": order_id,
            "error": "Payment service unavailable"
        }), 503


# ==========================================
# START SERVER
# ==========================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=8001
    )