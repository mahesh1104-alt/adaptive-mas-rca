from flask import Flask, jsonify
import requests
import os
import time

app = Flask(__name__)

INVENTORY_URL = os.getenv(
    "INVENTORY_URL",
    "http://localhost:8003"
)

FAIL_MODE = os.getenv(
    "FAIL_MODE",
    "false"
).lower() == "true"


@app.route("/health")
def health():
    return jsonify({
        "service": "payment-service",
        "status": "healthy"
    })


@app.route("/pay/<order_id>")
def process_payment(order_id):

    print(f"[PAYMENT] Processing payment for {order_id}")

    if FAIL_MODE:

        print("[PAYMENT][ERROR] Simulated payment failure")

        return jsonify({
            "status": "failed",
            "reason": "Simulated payment failure"
        }), 500

    try:

        response = requests.get(
            f"{INVENTORY_URL}/check/{order_id}",
            timeout=5
        )

        print(
            f"[PAYMENT] Inventory response: "
            f"{response.status_code}"
        )

        return jsonify({
            "status": "success",
            "inventory": response.json()
        })

    except Exception as e:

        print(
            f"[PAYMENT][ERROR] "
            f"Inventory service failed: {e}"
        )

        return jsonify({
            "status": "failed",
            "reason": "Inventory service unavailable"
        }), 503


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8002
    )