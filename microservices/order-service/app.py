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
        "order-service"
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

PAYMENT_URL = os.getenv(
    "PAYMENT_URL",
    "http://localhost:8002"
)


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
            "service": "order-service",
            "level": record.levelname,
            "message": record.getMessage()
        }

        return json.dumps(log)


logger = logging.getLogger(
    "order-service"
)

logger.setLevel(logging.INFO)

# Prevent duplicate handlers
if not logger.handlers:

    handler = logging.FileHandler(
        "/logs/order-service.jsonl"
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