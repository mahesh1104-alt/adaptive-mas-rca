from flask import Flask, jsonify

from prometheus_flask_exporter import PrometheusMetrics

import os
import time
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
        "inventory-service"
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


# ==========================================
# CONFIGURATION
# ==========================================

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
            "service": "inventory-service",
            "level": record.levelname,
            "message": record.getMessage()
        }

        return json.dumps(log)


logger = logging.getLogger(
    "inventory-service"
)

logger.setLevel(logging.INFO)

if not logger.handlers:

    handler = logging.FileHandler(
        "/logs/inventory-service.jsonl"
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

    # ======================================
    # SIMULATED INVENTORY FAILURE
    # ======================================

    if FAIL_MODE:

        logger.error(
            f"Simulated inventory timeout for {order_id}"
        )

        # Simulate slow/unavailable service
        time.sleep(10)

        return jsonify({
            "status": "timeout",
            "order_id": order_id
        }), 504


    # ======================================
    # NORMAL RESPONSE
    # ======================================

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