from flask import Flask, jsonify

from prometheus_flask_exporter import PrometheusMetrics

import requests
import os
import logging
import json

from datetime import datetime, timezone

# ==========================================
# OPENTELEMETRY
# ==========================================

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter
)
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor


# ==========================================
# FLASK APP
# ==========================================

app = Flask(__name__)

# Prometheus metrics
metrics = PrometheusMetrics(app)


# ==========================================
# OPENTELEMETRY CONFIGURATION
# ==========================================

resource = Resource.create({
    "service.name": os.getenv(
        "OTEL_SERVICE_NAME",
        "payment-service"
    )
})

trace_provider = TracerProvider(
    resource=resource
)

otlp_exporter = OTLPSpanExporter(
    endpoint=os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "http://jaeger:4317"
    ),
    insecure=True
)

trace_provider.add_span_processor(
    BatchSpanProcessor(otlp_exporter)
)

trace.set_tracer_provider(trace_provider)

# Instrument incoming Flask requests
FlaskInstrumentor().instrument_app(app)

# Instrument outgoing HTTP requests
RequestsInstrumentor().instrument()


# ==========================================
# CONFIGURATION
# ==========================================

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

os.makedirs(
    "/logs",
    exist_ok=True
)


class JSONFormatter(logging.Formatter):

    def format(self, record):

        log = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "service": "payment-service",
            "level": record.levelname,
            "message": record.getMessage()
        }

        return json.dumps(log)


logger = logging.getLogger(
    "payment-service"
)

logger.setLevel(logging.INFO)

if not logger.handlers:

    handler = logging.FileHandler(
        "/logs/payment-service.jsonl"
    )

    handler.setFormatter(
        JSONFormatter()
    )

    logger.addHandler(handler)


# ==========================================
# HEALTH CHECK
# ==========================================

@app.route("/health")
def health():

    logger.info(
        "Health check requested"
    )

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

    # ======================================
    # SIMULATED PAYMENT FAILURE
    # ======================================

    if FAIL_MODE:

        logger.error(
            f"Simulated payment failure for {order_id}"
        )

        return jsonify({
            "status": "failed",
            "reason": "Simulated payment failure"
        }), 500


    # ======================================
    # INVENTORY REQUEST
    # ======================================

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


    # ======================================
    # INVENTORY FAILURE
    # ======================================

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