from fastapi import FastAPI, HTTPException, Request, Query
import os
import json
import time
import base64
import urllib.request
import urllib.parse
import urllib.error
import requests
import ollama
import psycopg2
from psycopg2.extras import Json, RealDictCursor
from app.repository_connector import RepositoryConnector
from app.ingestion import router as ingestion_router
from app.storage import query_logs, query_metrics, query_traces
from app.source_preprocessing import preprocess_source
from app.feature_extraction import build_feature_bundle
from app.embedding_generation import generate_incident_embedding
from app.vector_store import search_similar_incidents

repository_connector = RepositoryConnector()

app = FastAPI(title="Adaptive MAS RCA API")
app.include_router(ingestion_router)

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

LOG_DIR = os.path.join(
    BASE_DIR,
    "logs"
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "llama3"
)


# ============================================================
# POSTGRESQL CONFIGURATION
# ============================================================

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

# ============================================================
# HISTORICAL INCIDENT RETRIEVAL
# ============================================================

def get_historical_incidents(
    service=None,
    alert_name=None,
    severity=None,
    limit=5
):
    """
    Retrieve similar historical incidents from PostgreSQL.

    Matching priority:
    1. Same service + alert name
    2. Same service
    3. Same alert name
    4. Other historical incidents
    """

    conn = None
    cursor = None

    try:
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB
        )

        cursor = conn.cursor(
            cursor_factory=RealDictCursor
        )

        conditions = []
        params = []

        if service:
            conditions.append("service = %s")
            params.append(service)

        if alert_name:
            conditions.append("alert_name = %s")
            params.append(alert_name)

        if severity:
            conditions.append("severity = %s")
            params.append(severity)

        where_clause = ""

        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
            SELECT
                incident_id,
                alert_name,
                service,
                severity,
                status,
                started_at,
                resolved_at,
                summary,
                description,
                root_cause,
                resolution
            FROM incidents
            {where_clause}
            ORDER BY started_at DESC
            LIMIT %s
        """

        params.append(limit)

        cursor.execute(query, params)

        incidents = cursor.fetchall()

        return [dict(incident) for incident in incidents]

    except Exception as e:

        print(
            f"Historical incident lookup failed: {e}"
        )

        return []

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


def format_historical_incidents(incidents):
    if not incidents:
        return "No matching historical incidents found."

    lines = []

    for incident in incidents:
        lines.append(
            f"""
Incident ID: {incident['incident_id']}
Alert: {incident['alert_name']}
Service: {incident['service']}
Severity: {incident['severity']}
Status: {incident['status']}
Summary: {incident['summary']}
Description: {incident['description']}
Root Cause: {incident['root_cause']}
Resolution: {incident['resolution']}
"""
        )

    return "\n".join(lines)


# ============================================================
# GITHUB CONFIGURATION
# ============================================================

GITHUB_API_URL = os.getenv(
    "GITHUB_API_URL",
    "https://api.github.com"
)

GITHUB_OWNER = os.getenv(
    "GITHUB_OWNER",
    "mahesh1104-alt"
)

GITHUB_REPO = os.getenv(
    "GITHUB_REPO",
    "adaptive-mas-rca"
)

GITHUB_BRANCH = os.getenv(
    "GITHUB_BRANCH",
    "develop"
)

GITHUB_TOKEN = os.getenv(
    "GITHUB_TOKEN",
    ""
)


# ============================================================
# REPOSITORY SERVICE MAPPING
# ============================================================
#
# Subtask 21 requirement:
# Map service names to repository paths.
#
# If config/repository_config.json exists, it will be loaded.
# Otherwise these defaults are used.
#
# ============================================================

DEFAULT_REPOSITORY_MAPPING = {
    "inventory-service": {
        "repository": "mahesh1104-alt/adaptive-mas-rca",
        "path": "microservices/inventory-service"
    },

    "order-service": {
        "repository": "mahesh1104-alt/adaptive-mas-rca",
        "path": "microservices/order-service"
    },

    "payment-service": {
        "repository": "mahesh1104-alt/adaptive-mas-rca",
        "path": "microservices/payment-service"
    },

    "log-collector": {
        "repository": "mahesh1104-alt/adaptive-mas-rca",
        "path": "log-collector"
    },

    "backend": {
        "repository": "mahesh1104-alt/adaptive-mas-rca",
        "path": "backend"
    },

    "frontend": {
        "repository": "mahesh1104-alt/adaptive-mas-rca",
        "path": "frontend"
    }
}


REPOSITORY_CONFIG_FILE = os.path.join(
    BASE_DIR,
    "config",
    "repository_config.json"
)


def load_repository_mapping():

    mapping = DEFAULT_REPOSITORY_MAPPING.copy()

    if not os.path.exists(
        REPOSITORY_CONFIG_FILE
    ):
        return mapping

    try:

        with open(
            REPOSITORY_CONFIG_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            custom_mapping = json.load(file)

        if isinstance(
            custom_mapping,
            dict
        ):

            mapping.update(
                custom_mapping
            )

        print(
            "Repository configuration loaded."
        )

    except Exception as e:

        print(
            f"Could not load repository configuration: {e}"
        )

    return mapping


REPOSITORY_MAPPING = load_repository_mapping()


# ============================================================
# LOCAL REPOSITORY CACHE
# ============================================================
#
# Cache prevents repeated GitHub network calls.
#
# Cache structure:
#
# {
#     "cache-key": {
#         "timestamp": ...,
#         "data": ...
#     }
# }
#
# ============================================================

REPOSITORY_CACHE = {}

CACHE_TTL = int(
    os.getenv(
        "REPOSITORY_CACHE_TTL",
        "300"
    )
)


def get_cached(
    key
):

    entry = REPOSITORY_CACHE.get(
        key
    )

    if not entry:
        return None

    age = (
        time.time()
        - entry["timestamp"]
    )

    if age > CACHE_TTL:

        REPOSITORY_CACHE.pop(
            key,
            None
        )

        return None

    return entry["data"]


def set_cached(
    key,
    data
):

    REPOSITORY_CACHE[key] = {
        "timestamp": time.time(),
        "data": data
    }


def clear_repository_cache():

    REPOSITORY_CACHE.clear()


# ============================================================
# POSTGRESQL CONNECTION
# ============================================================

def get_db_connection():

    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        database=POSTGRES_DB
    )


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def initialize_database():

    max_retries = 10

    for attempt in range(
        1,
        max_retries + 1
    ):

        connection = None
        cursor = None

        try:

            connection = get_db_connection()

            cursor = connection.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id SERIAL PRIMARY KEY,

                    fingerprint VARCHAR(255),

                    alert_name VARCHAR(255),

                    status VARCHAR(50),

                    service VARCHAR(255),

                    severity VARCHAR(50),

                    starts_at TIMESTAMPTZ,

                    ends_at TIMESTAMPTZ,

                    summary TEXT,

                    description TEXT,

                    labels JSONB,

                    annotations JSONB,

                    raw_payload JSONB,

                    received_at TIMESTAMPTZ
                    DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            # ------------------------------------------------
            # Migration for an older alerts table
            # ------------------------------------------------

            cursor.execute(
                """
                ALTER TABLE alerts
                ADD COLUMN IF NOT EXISTS fingerprint
                VARCHAR(255);
                """
            )

            cursor.execute(
                """
                ALTER TABLE alerts
                ADD COLUMN IF NOT EXISTS service
                VARCHAR(255);
                """
            )

            cursor.execute(
                """
                ALTER TABLE alerts
                ADD COLUMN IF NOT EXISTS severity
                VARCHAR(50);
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_alerts_fingerprint
                ON alerts(fingerprint);
                """
            )

            connection.commit()

            print(
                "PostgreSQL alerts table initialized."
            )

            return

        except Exception as e:

            print(
                f"PostgreSQL connection attempt "
                f"{attempt}/{max_retries} failed: {e}"
            )

            if attempt < max_retries:

                time.sleep(3)

        finally:

            if cursor:
                cursor.close()

            if connection:
                connection.close()

    print(
        "Could not initialize PostgreSQL "
        "after multiple attempts."
    )


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
def startup_event():

    initialize_database()


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health_check():

    return {
        "status": "healthy",
        "service": "adaptive-mas-rca-backend"
    }


# ============================================================
# DATABASE HEALTH CHECK
# ============================================================

@app.get("/health/database")
def database_health():

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor()

        cursor.execute(
            "SELECT 1"
        )

        cursor.fetchone()

        return {
            "status": "healthy",
            "database": "postgresql"
        }

    except Exception as e:

        raise HTTPException(
            status_code=503,
            detail=f"Database unavailable: {str(e)}"
        )

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# READ MICROSERVICE LOGS
# ============================================================

def read_logs():

    services = [
        "order-service",
        "payment-service",
        "inventory-service"
    ]

    events = []

    for service in services:

        log_file = os.path.join(
            LOG_DIR,
            f"{service}.jsonl"
        )

        if not os.path.exists(
            log_file
        ):
            continue

        with open(
            log_file,
            "r",
            encoding="utf-8"
        ) as file:

            for line in file:

                line = line.strip()

                if not line:
                    continue

                try:

                    events.append(
                        json.loads(line)
                    )

                except json.JSONDecodeError:

                    continue

    return events


# ============================================================
# SUBTASK 30
# INCIDENT FEATURE BUNDLE
# ============================================================

def build_incident_feature_bundle(
    incident_id,
    events,
):
    """
    Build one compact feature bundle for an RCA incident.

    Combines:
    - preprocessed logs
    - metrics
    - traces
    - relevant source code
    """

    if not events:
        return build_feature_bundle(
            incident_id=incident_id,
            logs=[],
            metrics=[],
            traces=[],
            source=[],
        )

    # --------------------------------------------------------
    # Incident time window
    # --------------------------------------------------------

    timestamps = [
        event.get("timestamp")
        for event in events
        if event.get("timestamp")
    ]

    timestamps = sorted(timestamps)

    start_time = timestamps[0] if timestamps else None
    end_time = timestamps[-1] if timestamps else None

    # --------------------------------------------------------
    # Services involved in the incident
    # --------------------------------------------------------

    services = sorted({
        event.get("service")
        for event in events
        if event.get("service")
    })

    # --------------------------------------------------------
    # Query metrics and traces for affected services
    # --------------------------------------------------------

    metrics = []
    traces = []

    for service in services:

        try:
            metric_result = query_metrics(
                service=service,
                start_time=start_time,
                end_time=end_time,
            )

            metrics.append({
                "service": service,
                "data": metric_result,
            })

        except Exception:
            # A failed metrics query should not prevent RCA.
            continue

        try:
            trace_result = query_traces(
                service=service,
                start_time=start_time,
                end_time=end_time,
            )

            traces.append({
                "service": service,
                "data": trace_result,
            })

        except Exception:
            # A failed trace query should not prevent RCA.
            continue

    # --------------------------------------------------------
    # Retrieve and preprocess relevant source
    # --------------------------------------------------------

    source = []

    for service in services:

        try:
            source_file = repository_connector.get_file(
                service,
                "app.py",
            )

            source_content = source_file.get(
                "content",
                "",
            )

            if not source_content:
                continue

            source_units = preprocess_source(
                source_content,
            )

            for unit in source_units:
                unit["service"] = service
                unit["file"] = source_file.get(
                    "path",
                    "app.py",
                )

            source.extend(source_units)

        except Exception:
            # Source retrieval should not prevent RCA.
            continue

    # --------------------------------------------------------
    # Build ONE compact bundle
    # --------------------------------------------------------

    return build_feature_bundle(
        incident_id=incident_id,
        logs=events,
        metrics=metrics,
        traces=traces,
        source=source,
    )


def get_similar_historical_incidents(
    feature_bundle,
    n_results=5,
):
    """
    Find historically similar incidents using semantic embeddings.

    The current incident feature bundle is converted into an embedding,
    then compared against historical incident embeddings stored in ChromaDB.
    """

    try:
        embedding = generate_incident_embedding(feature_bundle)

        results = search_similar_incidents(
            embedding=embedding,
            n_results=n_results,
        )

        similar_incidents = []

        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        documents = results.get("documents", [[]])[0]

        for index, incident_id in enumerate(ids):
            metadata = (
                metadatas[index]
                if index < len(metadatas)
                else {}
            )

            document = (
                documents[index]
                if index < len(documents)
                else ""
            )

            distance = (
                distances[index]
                if index < len(distances)
                else None
            )

            similar_incidents.append(
                {
                    "incident_id": incident_id,
                    "distance": distance,
                    "alert_name": metadata.get("alert_name", ""),
                    "service": metadata.get("service", ""),
                    "severity": metadata.get("severity", ""),
                    "status": metadata.get("status", ""),
                    "started_at": metadata.get("started_at", ""),
                    "resolved_at": metadata.get("resolved_at", ""),
                    "root_cause": metadata.get("root_cause", ""),
                    "resolution": metadata.get("resolution", ""),
                    "document": document,
                }
            )

        return similar_incidents

    except Exception as e:
        print(f"Semantic historical incident retrieval failed: {e}")
        return []


# ============================================================
# RCA ANALYSIS
# ============================================================
def analyze_with_llama(
    feature_bundle,
    similar_historical_incidents=None,
):

    feature_text = json.dumps(
        feature_bundle,
        indent=2,
        default=str
    )

    historical_context = ""

    if similar_historical_incidents:
        historical_lines = []

        for incident in similar_historical_incidents:
            historical_lines.append(
                f"""
Incident ID: {incident.get('incident_id', '')}
Similarity Distance: {incident.get('distance', '')}
Alert: {incident.get('alert_name', '')}
Service: {incident.get('service', '')}
Severity: {incident.get('severity', '')}
Summary: {incident.get('document', '')}
Historical Root Cause: {incident.get('root_cause', '')}
Historical Resolution: {incident.get('resolution', '')}
"""
            )

        historical_context = "\n".join(historical_lines)

    if not historical_context:
        historical_context = "No similar historical incidents were found."

    prompt = f"""

You are an expert Root Cause Analysis assistant
for a distributed microservice system.

Analyze the following logs carefully.

IMPORTANT RCA RULES:

1. Identify the EARLIEST actual failure.

2. Do NOT automatically classify a timeout as a
   network failure.

3. If a log explicitly says "Simulated ... failure",
   treat that as the root cause.

4. Distinguish ROOT CAUSE from downstream symptoms.

5. A service failing because another service failed is
   a downstream effect.

6. Use timestamps and service names to reconstruct
   failure propagation.

7. Only claim a network problem when there is actual
   evidence of a network/connectivity failure.

8. Do not invent evidence.

9. Use similar historical incidents as supporting
   evidence, not as definitive proof.

10. Do NOT copy the root cause of a historical incident
    unless the current incident evidence supports it.

11. Give higher priority to evidence from the current
    incident than historical similarity.

Return these sections:

1. Incident

2. Failure Symptoms

3. Root Cause

4. Root Cause Service

5. Evidence

6. Failure Propagation

7. Confidence

8. Recommended Remediation


============================================================
CURRENT INCIDENT FEATURE BUNDLE
============================================================

{feature_text}


============================================================
SIMILAR HISTORICAL INCIDENTS
============================================================

{historical_context}

Use the historical incidents above to help identify
patterns and possible causes.

However, historical incidents are only references.
The final RCA must be based primarily on evidence
contained in the CURRENT INCIDENT FEATURE BUNDLE.

"""
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response[
        "message"
    ][
        "content"
    ]


# ============================================================
# RCA API ENDPOINT
# ============================================================

@app.post("/api/rca/analyze")
def run_rca():

    events = read_logs()

    if not events:

        raise HTTPException(
            status_code=404,
            detail="No microservice logs found"
        )

    feature_bundle = build_incident_feature_bundle(
        incident_id="RCA-LIVE",
        events=events,
    )

    similar_historical_incidents = get_similar_historical_incidents(
        feature_bundle,
        n_results=5,
    )

    print()
    print("=" * 60)
    print("SEMANTIC HISTORICAL INCIDENTS")
    print("=" * 60)

    for incident in similar_historical_incidents:
        print(
            f"{incident['incident_id']} | "
            f"distance={incident['distance']} | "
            f"service={incident['service']} | "
            f"alert={incident['alert_name']}"
        )

    print("=" * 60)

    try:

        result = analyze_with_llama(
            feature_bundle,
            similar_historical_incidents,
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"RCA analysis failed: {str(e)}"
        )

    os.makedirs(
        LOG_DIR,
        exist_ok=True
    )

    result_file = os.path.join(
        LOG_DIR,
        "rca_result.txt"
    )

    with open(
        result_file,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(result)

    return {
        "status": "success",
        "model": OLLAMA_MODEL,
        "events_analyzed": len(events),
        "feature_bundle": feature_bundle,
        "root_cause_analysis": result
    }


# ============================================================
# ALERTMANAGER WEBHOOK
# ============================================================

@app.post("/api/alerts/webhook")
async def alertmanager_webhook(
    request: Request
):

    try:

        payload = await request.json()

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Invalid JSON payload"
        )

    alerts = payload.get(
        "alerts",
        []
    )

    if not isinstance(
        alerts,
        list
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid Alertmanager payload: "
                "alerts must be a list"
            )
        )

    stored_alerts = []

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor()

        for alert in alerts:

            labels = alert.get(
                "labels",
                {}
            )

            annotations = alert.get(
                "annotations",
                {}
            )

            alert_name = labels.get(
                "alertname",
                "unknown"
            )

            service = labels.get(
                "service",
                labels.get(
                    "job",
                    labels.get(
                        "instance",
                        "unknown"
                    )
                )
            )

            status = alert.get(
                "status",
                payload.get(
                    "status",
                    "unknown"
                )
            )

            severity = labels.get(
                "severity",
                "unknown"
            )

            fingerprint = alert.get(
                "fingerprint"
            )

            starts_at = alert.get(
                "startsAt"
            )

            ends_at = alert.get(
                "endsAt"
            )

            summary = annotations.get(
                "summary",
                ""
            )

            description = annotations.get(
                "description",
                ""
            )

            # ------------------------------------------------
            # If fingerprint exists, update existing alert.
            # This prevents duplicate rows when an alert
            # changes from firing -> resolved.
            # ------------------------------------------------

            if fingerprint:

                cursor.execute(
                    """
                    SELECT id
                    FROM alerts
                    WHERE fingerprint = %s
                    ORDER BY id DESC
                    LIMIT 1;
                    """,
                    (
                        fingerprint,
                    )
                )

                existing = cursor.fetchone()

            else:

                existing = None

            if existing:

                alert_id = existing[0]

                cursor.execute(
                    """
                    UPDATE alerts
                    SET
                        alert_name = %s,
                        status = %s,
                        service = %s,
                        severity = %s,
                        starts_at = %s,
                        ends_at = %s,
                        summary = %s,
                        description = %s,
                        labels = %s,
                        annotations = %s,
                        raw_payload = %s,
                        received_at =
                            CURRENT_TIMESTAMP
                    WHERE id = %s;
                    """,
                    (
                        alert_name,
                        status,
                        service,
                        severity,
                        starts_at,
                        ends_at,
                        summary,
                        description,
                        Json(labels),
                        Json(annotations),
                        Json(alert),
                        alert_id
                    )
                )

                operation = "updated"

            else:

                cursor.execute(
                    """
                    INSERT INTO alerts (
                        fingerprint,
                        alert_name,
                        status,
                        service,
                        severity,
                        starts_at,
                        ends_at,
                        summary,
                        description,
                        labels,
                        annotations,
                        raw_payload
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    RETURNING id;
                    """,
                    (
                        fingerprint,
                        alert_name,
                        status,
                        service,
                        severity,
                        starts_at,
                        ends_at,
                        summary,
                        description,
                        Json(labels),
                        Json(annotations),
                        Json(alert)
                    )
                )

                alert_id = cursor.fetchone()[0]

                operation = "created"

            stored_alerts.append(
                {
                    "id": alert_id,
                    "fingerprint": fingerprint,
                    "alert_name": alert_name,
                    "status": status,
                    "service": service,
                    "severity": severity,
                    "operation": operation
                }
            )

        connection.commit()

    except Exception as e:

        if connection:
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to store alerts: {str(e)}"
        )

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()

    return {
        "status": "success",
        "message": "Alertmanager payload received",
        "alerts_received": len(alerts),
        "alerts_stored": stored_alerts
    }


# ============================================================
# GET STORED ALERTS
# ============================================================

@app.get("/api/alerts")
def get_alerts():

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(
            cursor_factory=RealDictCursor
        )

        cursor.execute(
            """
            SELECT
                id,
                fingerprint,
                alert_name,
                status,
                service,
                severity,
                starts_at,
                ends_at,
                summary,
                description,
                labels,
                annotations,
                received_at
            FROM alerts
            ORDER BY received_at DESC;
            """
        )

        alerts = cursor.fetchall()

        return {
            "count": len(alerts),
            "alerts": alerts
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve alerts: {str(e)}"
        )

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# GET SINGLE ALERT
# ============================================================

@app.get("/api/alerts/{alert_id}")
def get_alert(
    alert_id: int
):

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(
            cursor_factory=RealDictCursor
        )

        cursor.execute(
            """
            SELECT
                id,
                fingerprint,
                alert_name,
                status,
                service,
                severity,
                starts_at,
                ends_at,
                summary,
                description,
                labels,
                annotations,
                raw_payload,
                received_at
            FROM alerts
            WHERE id = %s;
            """,
            (
                alert_id,
            )
        )

        alert = cursor.fetchone()

        if not alert:

            raise HTTPException(
                status_code=404,
                detail="Alert not found"
            )

        return alert

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve alert: {str(e)}"
        )

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# DELETE ALL ALERTS
# ============================================================

@app.delete("/api/alerts")
def delete_alerts():

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor()

        cursor.execute(
            "DELETE FROM alerts"
        )

        deleted_count = cursor.rowcount

        connection.commit()

        return {
            "status": "success",
            "deleted": deleted_count
        }

    except Exception as e:

        if connection:
            connection.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete alerts: {str(e)}"
        )

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# ============================================================
# SUBTASK 21
# SOURCE CODE REPOSITORY CONNECTOR
# ============================================================
#
# Features:
#
# 1. Map service -> repository path
# 2. Retrieve repository files
# 3. Retrieve a specific source file
# 4. Retrieve latest 5 commits
# 5. Local caching
#
# ============================================================


# ============================================================
# GITHUB HTTP HELPER
# ============================================================

def github_request(
    endpoint
):

    url = (
        GITHUB_API_URL.rstrip("/")
        + "/"
        + endpoint.lstrip("/")
    )

    headers = {
        "Accept": (
            "application/vnd.github+json"
        ),
        "User-Agent": (
            "Adaptive-MAS-RCA"
        ),
        "X-GitHub-Api-Version": (
            "2022-11-28"
        )
    }

    if GITHUB_TOKEN:

        headers[
            "Authorization"
        ] = (
            f"Bearer {GITHUB_TOKEN}"
        )

    request = urllib.request.Request(
        url,
        headers=headers,
        method="GET"
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=15
        ) as response:

            body = response.read()

            return json.loads(
                body.decode("utf-8")
            )

    except urllib.error.HTTPError as e:

        error_body = ""

        try:

            error_body = e.read().decode(
                "utf-8"
            )
        except Exception:
            pass

        raise HTTPException(
            status_code=e.code,
            detail=(
                f"GitHub API error: "
                f"{error_body}"
            )
        )

    except urllib.error.URLError as e:

        raise HTTPException(
            status_code=503,
            detail=(
                f"Unable to connect to GitHub: "
                f"{str(e)}"
            )
        )


# ============================================================
# GET SERVICE REPOSITORY CONFIG
# ============================================================

def get_service_repository(
    service_name
):

    config = REPOSITORY_MAPPING.get(
        service_name
    )

    if not config:

        raise HTTPException(
            status_code=404,
            detail=(
                f"No repository mapping found "
                f"for service '{service_name}'"
            )
        )

    repository = config.get(
        "repository"
    )

    path = config.get(
        "path",
        ""
    )

    if not repository:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Invalid repository configuration "
                f"for service '{service_name}'"
            )
        )

    return {
        "service": service_name,
        "repository": repository,
        "path": path
    }


# ============================================================
# GET REPOSITORY FILE TREE
# ============================================================

def fetch_repository_files(
    repository,
    path,
    branch
):

    cache_key = (
        f"files:{repository}:"
        f"{path}:{branch}"
    )

    cached = get_cached(
        cache_key
    )

    if cached is not None:

        return cached

    encoded_path = urllib.parse.quote(
        path.strip("/"),
        safe="/"
    )

    endpoint = (
        f"repos/{repository}/contents/"
        f"{encoded_path}"
        f"?ref={urllib.parse.quote(branch)}"
    )

    data = github_request(
        endpoint
    )

    files = []

    # --------------------------------------------------------
    # Directory response
    # --------------------------------------------------------

    if isinstance(
        data,
        list
    ):

        for item in data:

            files.append(
                {
                    "name": item.get(
                        "name"
                    ),
                    "path": item.get(
                        "path"
                    ),
                    "type": item.get(
                        "type"
                    ),
                    "size": item.get(
                        "size"
                    ),
                    "url": item.get(
                        "html_url"
                    )
                }
            )

    # --------------------------------------------------------
    # Single file response
    # --------------------------------------------------------

    elif isinstance(
        data,
        dict
    ):

        files.append(
            {
                "name": data.get(
                    "name"
                ),
                "path": data.get(
                    "path"
                ),
                "type": data.get(
                    "type"
                ),
                "size": data.get(
                    "size"
                ),
                "url": data.get(
                    "html_url"
                )
            }
        )

    set_cached(
        cache_key,
        files
    )

    return files


# ============================================================
# GET SOURCE FILE
# ============================================================

def fetch_source_file(
    repository,
    file_path,
    branch
):

    cache_key = (
        f"file:{repository}:"
        f"{file_path}:{branch}"
    )

    cached = get_cached(
        cache_key
    )

    if cached is not None:

        return cached

    encoded_path = urllib.parse.quote(
        file_path.strip("/"),
        safe="/"
    )

    endpoint = (
        f"repos/{repository}/contents/"
        f"{encoded_path}"
        f"?ref={urllib.parse.quote(branch)}"
    )

    data = github_request(
        endpoint
    )

    if not isinstance(
        data,
        dict
    ):

        raise HTTPException(
            status_code=404,
            detail="Source file not found"
        )

    if data.get(
        "type"
    ) != "file":

        raise HTTPException(
            status_code=400,
            detail="Requested path is not a file"
        )

    encoded_content = data.get(
        "content",
        ""
    )

    try:

        content = base64.b64decode(
            encoded_content
        ).decode(
            "utf-8"
        )

    except UnicodeDecodeError:

        content = base64.b64decode(
            encoded_content
        ).decode(
            "utf-8",
            errors="replace"
        )

    result = {
        "name": data.get(
            "name"
        ),
        "path": data.get(
            "path"
        ),
        "size": data.get(
            "size"
        ),
        "sha": data.get(
            "sha"
        ),
        "html_url": data.get(
            "html_url"
        ),
        "content": content
    }

    set_cached(
        cache_key,
        result
    )

    return result


# ============================================================
# GET RECENT COMMITS
# ============================================================

def fetch_recent_commits(
    repository,
    path,
    branch,
    limit=5
):

    limit = min(
        max(
            int(limit),
            1
        ),
        20
    )

    cache_key = (
        f"commits:{repository}:"
        f"{path}:{branch}:{limit}"
    )

    cached = get_cached(
        cache_key
    )

    if cached is not None:

        return cached

    params = urllib.parse.urlencode(
        {
            "sha": branch,
            "path": path,
            "per_page": limit
        }
    )

    endpoint = (
        f"repos/{repository}/commits"
        f"?{params}"
    )

    data = github_request(
        endpoint
    )

    commits = []

    if isinstance(
        data,
        list
    ):

        for commit in data:

            commit_info = commit.get(
                "commit",
                {}
            )

            author_info = commit_info.get(
                "author",
                {}
            )

            commits.append(
                {
                    "sha": commit.get(
                        "sha"
                    ),
                    "message": commit_info.get(
                        "message"
                    ),
                    "author": author_info.get(
                        "name"
                    ),
                    "date": author_info.get(
                        "date"
                    ),
                    "html_url": commit.get(
                        "html_url"
                    )
                }
            )

    set_cached(
        cache_key,
        commits
    )

    return commits


# ============================================================
# REPOSITORY CONNECTOR
#
# Given a service name:
#
# /api/repository/inventory-service
#
# returns:
#
# - repository
# - service path
# - source files
# - latest 5 commits
#
# ============================================================

@app.get(
    "/api/repository/{service_name}"
)
def get_repository_information(
    service_name: str,
    branch: str = Query(
        default=GITHUB_BRANCH
    )
):

    repository_info = get_service_repository(
        service_name
    )

    repository = repository_info[
        "repository"
    ]

    path = repository_info[
        "path"
    ]

    files = fetch_repository_files(
        repository,
        path,
        branch
    )

    commits = fetch_recent_commits(
        repository,
        path,
        branch,
        5
    )

    return {
        "status": "success",
        "service": service_name,
        "repository": repository,
        "path": path,
        "branch": branch,
        "files": files,
        "recent_commits": commits,
        "cached": True
    }


# ============================================================
# GET SOURCE FILE FOR SERVICE
#
# Example:
#
# GET
# /api/repository/inventory-service/file
#     ?path=microservices/inventory-service/app.py
#
# ============================================================

@app.get(
    "/api/repository/{service_name}/file"
)
def get_repository_file(
    service_name: str,
    path: str = Query(...),
    branch: str = Query(
        default=GITHUB_BRANCH
    )
):

    repository_info = get_service_repository(
        service_name
    )

    repository = repository_info[
        "repository"
    ]

    service_root = repository_info[
        "path"
    ].strip("/")

    requested_path = path.strip("/")

    # --------------------------------------------------------
    # Security / scope check
    #
    # Prevent requesting arbitrary files outside the
    # configured service repository path.
    # --------------------------------------------------------

    if not (
        requested_path == service_root
        or requested_path.startswith(
            service_root + "/"
        )
    ):

        raise HTTPException(
            status_code=403,
            detail=(
                "Requested file is outside "
                "the configured service path"
            )
        )

    file_data = fetch_source_file(
        repository,
        requested_path,
        branch
    )

    return {
        "status": "success",
        "service": service_name,
        "repository": repository,
        "branch": branch,
        "file": file_data
    }

# ============================================================
# PREPROCESS SOURCE FILE FOR SERVICE
# ============================================================

@app.get(
    "/api/repository/{service_name}/preprocess"
)
def preprocess_repository_file(
    service_name: str,
    path: str = Query(...),
    fault_line: int = Query(
        default=None,
        ge=1
    ),
    context_lines: int = Query(
        default=20,
        ge=0
    ),
    branch: str = Query(
        default=GITHUB_BRANCH
    )
):

    repository_info = get_service_repository(
        service_name
    )

    repository = repository_info[
        "repository"
    ]

    service_root = repository_info[
        "path"
    ].strip("/")

    requested_path = path.strip("/")

    # --------------------------------------------------------
    # Security / scope check
    # --------------------------------------------------------

    if not (
        requested_path == service_root
        or requested_path.startswith(
            service_root + "/"
        )
    ):

        raise HTTPException(
            status_code=403,
            detail=(
                "Requested file is outside "
                "the configured service path"
            )
        )

    # --------------------------------------------------------
    # Retrieve source code
    # --------------------------------------------------------

    file_data = fetch_source_file(
        repository,
        requested_path,
        branch
    )

    source = file_data.get(
        "content",
        ""
    )

    # --------------------------------------------------------
    # Preprocess source code
    # --------------------------------------------------------

    try:

        units = preprocess_source(
            source,
            fault_line=fault_line,
            context_lines=context_lines
        )

    except SyntaxError as e:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Unable to parse source file: {e}"
            )
        )

    return {
        "status": "success",
        "service": service_name,
        "repository": repository,
        "branch": branch,
        "file": {
            "name": file_data.get("name"),
            "path": file_data.get("path"),
            "size": file_data.get("size"),
            "sha": file_data.get("sha"),
            "html_url": file_data.get("html_url")
        },
        "fault_line": fault_line,
        "context_lines": context_lines,
        "units": units
    }


# ============================================================
# GET RECENT COMMITS FOR SERVICE
#
# Example:
#
# /api/repository/inventory-service/commits
#
# ============================================================

@app.get(
    "/api/repository/{service_name}/commits"
)
def get_repository_commits(
    service_name: str,
    limit: int = Query(
        default=5,
        ge=1,
        le=20
    ),
    branch: str = Query(
        default=GITHUB_BRANCH
    )
):

    repository_info = get_service_repository(
        service_name
    )

    repository = repository_info[
        "repository"
    ]

    path = repository_info[
        "path"
    ]

    commits = fetch_recent_commits(
        repository,
        path,
        branch,
        limit
    )

    return {
        "status": "success",
        "service": service_name,
        "repository": repository,
        "path": path,
        "branch": branch,
        "count": len(commits),
        "commits": commits
    }


# ============================================================
# LIST CONFIGURED SERVICES
# ============================================================

@app.get(
    "/api/repository/services"
)
def list_repository_services():

    services = []

    for service_name, config in (
        REPOSITORY_MAPPING.items()
    ):

        services.append(
            {
                "service": service_name,
                "repository": config.get(
                    "repository"
                ),
                "path": config.get(
                    "path"
                )
            }
        )

    return {
        "status": "success",
        "count": len(services),
        "services": services
    }


# ============================================================
# CLEAR REPOSITORY CACHE
# ============================================================

@app.delete(
    "/api/repository/cache"
)
def clear_repository_cache_endpoint():

    count = len(
        REPOSITORY_CACHE
    )

    clear_repository_cache()

    return {
        "status": "success",
        "message": "Repository cache cleared",
        "entries_removed": count
    }

@app.get("/api/repository/{service_name}/file/{file_path:path}")
def get_repository_file(service_name: str, file_path: str):
    try:
        result = repository_connector.get_file(
            service_name,
            file_path
        )

        return {
            "status": "success",
            **result
        }

    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )

    except requests.HTTPError as e:
        raise HTTPException(
            status_code=502,
            detail=f"GitHub API error: {e}"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# STORAGE QUERY ENDPOINTS
# ============================================================

@app.get("/api/storage/logs")
def get_storage_logs(
    service: str = Query(...),
    start_time: str = Query(None),
    end_time: str = Query(None),
):
    """
    Query raw logs for a service within an optional time range.
    """

    return {
        "service": service,
        "start_time": start_time,
        "end_time": end_time,
        "data": query_logs(
            service=service,
            start_time=start_time,
            end_time=end_time,
        ),
    }


@app.get("/api/storage/metrics")
def get_storage_metrics(
    service: str = Query(...),
    start_time:str = Query(None),
    end_time: str = Query(None),
    metric_name: str = Query(None),
):
    """
    Query Prometheus metrics for a service.
    """

    return query_metrics(
        service=service,
        start_time=start_time,
        end_time=end_time,
        metric_name=metric_name,
    )


@app.get("/api/storage/traces")
def get_storage_traces(
    service: str = Query(...),
    start_time: str = Query(None),
    end_time: str = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Query Jaeger traces for a service.
    """

    return query_traces(
        service=service,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )

# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )