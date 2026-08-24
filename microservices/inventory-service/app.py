from flask import Flask, jsonify
from prometheus_flask_exporter import PrometheusMetrics
import os
import time
import logging
import json
from datetime import datetime, timezone

app = Flask(__name__)

metrics = PrometheusMetrics(app)

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
            "service": "inventory-service",
            "level": record.levelname,
            "message": record.getMessage()
        }

        return json.dumps(log)


logger = logging.getLogger("inventory-service")
logger.setLevel(logging.INFO)

if not logger.handlers:

    handler = logging.FileHandler(
        "/logs/inventory-service.jsonl"
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
        "service": "inventory-service",
        "status": "healthy"
    })


# ==========================================
# CHECK INVENTORY
# ==========================================

@app.route("/check/<order_id>")
def check_inventory(order_id):

    logger.info(
        f"Checking inventory for {order_id}"
    )

    # ------------------------------------------
    # SIMULATED FAILURE
    # ------------------------------------------

    if FAIL_MODE:

        logger.error(
            f"Simulated inventory timeout for {order_id}"
        )

        time.sleep(10)

        return jsonify({
            "status": "timeout"
        }), 504

    # ------------------------------------------
    # NORMAL RESPONSE
    # ------------------------------------------

    logger.info(
        f"Inventory available for {order_id}"
    )

    return jsonify({
        "status": "available",
        "order_id": order_id,
        "quantity": 10
    })


# ==========================================
# START SERVER
# ==========================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=8003
    )