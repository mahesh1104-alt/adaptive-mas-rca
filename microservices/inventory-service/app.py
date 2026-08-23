from flask import Flask, jsonify
import os
import time

app = Flask(__name__)

FAIL_MODE = os.getenv(
    "FAIL_MODE",
    "false"
).lower() == "true"


@app.route("/health")
def health():
    return jsonify({
        "service": "inventory-service",
        "status": "healthy"
    })


@app.route("/check/<order_id>")
def check_inventory(order_id):

    print(
        f"[INVENTORY] Checking inventory "
        f"for {order_id}"
    )

    if FAIL_MODE:

        print(
            "[INVENTORY][ERROR] "
            "Simulated inventory timeout"
        )

        time.sleep(10)

        return jsonify({
            "status": "timeout"
        }), 504

    return jsonify({
        "status": "available",
        "order_id": order_id,
        "quantity": 10
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8003
    )