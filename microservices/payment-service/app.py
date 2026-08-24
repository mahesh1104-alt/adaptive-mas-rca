from flask import Flask, jsonify
import requests
import os
import logging
import json
from datetime import datetime, timezone

app = Flask(__name__)

INVENTORY_URL = os.getenv(
    "INVENTORY_URL",
    "http://localhost:8003"
)

FAIL_MODE = os.getenv(
    "FAIL_MODE",
    "false"
).lower() == "true"


# ==========================================
# JSON LOGGER
# ==========================================

os.makedirs("/logs", exist_ok=True)


class JSONFormatter(logging.Formatter):

    def format(self, record):
        log = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "payment-service",
            "level": record.levelname,
            "message": record.getMessage()
        }

        return json.dumps(log)


logger = logging.getLogger("payment-service")
logger.setLevel(logging.INFO)

if not logger.handlers:

    handler = logging.FileHandler(
        "/logs/payment-service.jsonl"
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
        "service": "payment-service",
        "status": "healthy"
    })


# ==========================================
# PROCESS PAYMENT
# ==========================================

@app.route("/pay/<order_id>")
def process_payment(order_id):

    logger.info(
        f"Processing payment for {order_id}"
    )

    # ------------------------------------------
    # SIMULATED FAILURE
    # ------------------------------------------

    if FAIL_MODE:

        logger.error(
            f"Simulated payment failure for {order_id}"
        )

        return jsonify({
            "status": "failed",
            "reason": "Simulated payment failure"
        }), 500

    # ------------------------------------------
    # INVENTORY REQUEST
    # ------------------------------------------

    try:

        response = requests.get(
            f"{INVENTORY_URL}/check/{order_id}",
            timeout=5
        )

        logger.info(
            f"Inventory service returned status "
            f"{response.status_code}"
        )

        return jsonify({
            "status": "success",
            "inventory": response.json()
        }), response.status_code

    # ------------------------------------------
    # INVENTORY FAILURE
    # ------------------------------------------

    except Exception as e:

        logger.error(
            f"Inventory service failed: {str(e)}"
        )

        return jsonify({
            "status": "failed",
            "reason": "Inventory service unavailable"
        }), 503


# ==========================================
# START SERVER
# ==========================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=8002
    )