from flask import Flask, jsonify
import requests
import os
import time

app = Flask(__name__)

PAYMENT_URL = os.getenv(
    "PAYMENT_URL",
    "http://localhost:8002"
)

@app.route("/health")
def health():
    return jsonify({
        "service": "order-service",
        "status": "healthy"
    })


@app.route("/order/<order_id>")
def create_order(order_id):

    print(f"[ORDER] Creating order {order_id}")

    try:
        response = requests.get(
            f"{PAYMENT_URL}/pay/{order_id}",
            timeout=5
        )

        print(
            f"[ORDER] Payment response: "
            f"{response.status_code}"
        )

        return jsonify({
            "order_id": order_id,
            "payment_status": response.json()
        })

    except Exception as e:

        print(f"[ORDER][ERROR] Payment service failed: {e}")

        return jsonify({
            "order_id": order_id,
            "error": "Payment service unavailable"
        }), 503


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8001
    )