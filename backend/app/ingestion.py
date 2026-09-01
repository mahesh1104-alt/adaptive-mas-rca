from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime, timezone

import os
import json
import requests

import psycopg2
from psycopg2.extras import Json

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter
)


router = APIRouter(
    prefix="/api/ingest",
    tags=["Unified Data Ingestion"]
)


# ============================================================
# CONFIGURATION
# ============================================================

LOG_DIR = os.getenv(
    "LOG_DIR",
    "/logs"
)

PUSHGATEWAY_URL = os.getenv(
    "PUSHGATEWAY_URL",
    "http://pushgateway:9091"
)

POSTGRES_HOST = os.getenv(
    "POSTGRES_HOST",
    "postgres"
)

POSTGRES_PORT = int(
    os.getenv(
        "POSTGRES_PORT",
        "5432"
    )
)

POSTGRES_USER = os.getenv(
    "POSTGRES_USER",
    "rca_user"
)

POSTGRES_PASSWORD = os.getenv(
    "POSTGRES_PASSWORD",
    "rca_password"
)

POSTGRES_DB = os.getenv(
    "POSTGRES_DB",
    "rca_db"
)

OTEL_ENDPOINT = os.getenv(
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "http://jaeger:4317"
)


# ============================================================
# PYDANTIC MODELS
# ============================================================

class LogPayload(BaseModel):
    timestamp: Optional[str] = None
    service: str = Field(min_length=1)
    level: str = Field(min_length=1)
    message: str = Field(min_length=1)


class MetricPayload(BaseModel):
    name: str = Field(
        min_length=1,
        pattern=r"^[a-zA-Z_:][a-zA-Z0-9_:]*$"
    )
    value: float
    labels: Dict[str, str] = {}


class TracePayload(BaseModel):
    trace_id: str = Field(min_length=1)
    service: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    timestamp: Optional[str] = None
    attributes: Dict[str, Any] = {}


class AlertPayload(BaseModel):
    alert_name: str = Field(min_length=1)
    service: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    status: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    description: Optional[str] = None


# ============================================================
# LOG INGESTION
# ============================================================

@router.post("/logs")
def ingest_log(payload: LogPayload):

    timestamp = payload.timestamp

    if not timestamp:
        timestamp = datetime.now(
            timezone.utc
        ).isoformat()

    log_event = {
        "timestamp": timestamp,
        "service": payload.service,
        "level": payload.level,
        "message": payload.message
    }

    os.makedirs(
        LOG_DIR,
        exist_ok=True
    )

    log_file = os.path.join(
        LOG_DIR,
        f"{payload.service}.jsonl"
    )

    try:

        with open(
            log_file,
            "a",
            encoding="utf-8"
        ) as file:

            file.write(
                json.dumps(log_event) + "\n"
            )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to store log: {str(e)}"
        )

    return {
        "status": "accepted",
        "type": "log",
        "service": payload.service
    }


# ============================================================
# METRIC INGESTION
# ============================================================

@router.post("/metrics")
def ingest_metric(payload: MetricPayload):

    labels = {
        "service": "unified-ingestion",
        **payload.labels
    }

    label_string = ",".join(
        f'{key}="{value}"'
        for key, value in labels.items()
    )

    metric_line = (
        f"{payload.name}"
        f"{{{label_string}}} "
        f"{payload.value}\n"
    )

    try:

        response = requests.post(
            f"{PUSHGATEWAY_URL}/metrics/job/unified-ingestion",
            data=metric_line,
            headers={
                "Content-Type":
                    "text/plain"
            },
            timeout=10
        )

        if not response.ok:

            raise RuntimeError(
                f"Pushgateway returned "
                f"{response.status_code}: "
                f"{response.text}"
            )

    except Exception as e:

        raise HTTPException(
            status_code=502,
            detail=f"Failed to ingest metric: {str(e)}"
        )

    return {
        "status": "accepted",
        "type": "metric",
        "name": payload.name,
        "value": payload.value
    }


# ============================================================
# TRACE INGESTION
# ============================================================

trace_resource = Resource.create({
    "service.name": "unified-ingestion"
})

trace_provider = TracerProvider(
    resource=trace_resource
)

trace_exporter = OTLPSpanExporter(
    endpoint=OTEL_ENDPOINT,
    insecure=True
)

trace_provider.add_span_processor(
    BatchSpanProcessor(trace_exporter)
)

trace.set_tracer_provider(
    trace_provider
)

tracer = trace.get_tracer(
    "unified-ingestion"
)


@router.post("/traces")
def ingest_trace(payload: TracePayload):

    try:

        with tracer.start_as_current_span(
            payload.operation
        ) as span:

            span.set_attribute(
                "ingestion.trace_id",
                payload.trace_id
            )

            span.set_attribute(
                "service.name",
                payload.service
            )

            for key, value in payload.attributes.items():

                span.set_attribute(
                    str(key),
                    str(value)
                )

        trace_provider.force_flush()

    except Exception as e:

        raise HTTPException(
            status_code=502,
            detail=f"Failed to ingest trace: {str(e)}"
        )

    return {
        "status": "accepted",
        "type": "trace",
        "trace_id": payload.trace_id,
        "service": payload.service
    }


# ============================================================
# ALERT INGESTION
# ============================================================

@router.post("/alerts")
def ingest_alert(payload: AlertPayload):

    connection = None
    cursor = None

    try:

        connection = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB
        )

        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO alerts (
                alert_name,
                service,
                severity,
                status,
                summary,
                description
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                payload.alert_name,
                payload.service,
                payload.severity,
                payload.status,
                payload.summary,
                payload.description
            )
        )

        connection.commit()

    except Exception as e:

        if connection:
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to store alert: {str(e)}"
        )

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()

    return {
        "status": "accepted",
        "type": "alert",
        "service": payload.service,
        "alert_name": payload.alert_name
    }