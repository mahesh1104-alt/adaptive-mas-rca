from fastapi import FastAPI, HTTPException, Request
import os
import json
import time
import hashlib

import ollama
import psycopg2

from psycopg2.extras import Json, RealDictCursor


app = FastAPI(title="Adaptive MAS RCA API")


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
# DATABASE CONNECTION
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

            # ------------------------------------------------
            # Create alerts table
            # ------------------------------------------------

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
            # Migration for older database
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

            # ------------------------------------------------
            # Index fingerprint for faster lookup
            # ------------------------------------------------

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

            if connection:
                connection.rollback()

            if attempt < max_retries:

                time.sleep(3)

            else:

                print(
                    "Could not initialize PostgreSQL "
                    "after multiple attempts."
                )

        finally:

            if cursor:
                cursor.close()

            if connection:
                connection.close()


# ============================================================
# APPLICATION STARTUP
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

        try:

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

        except Exception as e:

            print(
                f"Error reading {log_file}: {e}"
            )

    return events


# ============================================================
# RCA ANALYSIS
# ============================================================

def analyze_with_llama(events):

    log_text = "\n".join(
        json.dumps(event)
        for event in events
    )

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

9. Alertmanager alerts should be treated as incident
   signals and not automatically as the root cause.

Return exactly these sections:

1. Incident
2. Failure Symptoms
3. Root Cause
4. Root Cause Service
5. Evidence
6. Failure Propagation
7. Confidence
8. Recommended Remediation

Logs:

{log_text}
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

    try:

        result = analyze_with_llama(
            events
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"RCA analysis failed: {str(e)}"
        )

    # --------------------------------------------------------
    # Save RCA result
    # --------------------------------------------------------

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
        "root_cause_analysis": result
    }


# ============================================================
# GENERATE FALLBACK FINGERPRINT
# ============================================================

def generate_fingerprint(
    alert_name,
    labels
):

    """
    Alertmanager normally provides a fingerprint.

    If fingerprint is missing, generate a deterministic
    fingerprint from alertname + sorted labels.

    This prevents duplicate rows for the same alert.
    """

    fingerprint_data = {
        "alertname": alert_name,
        "labels": labels
    }

    fingerprint_string = json.dumps(
        fingerprint_data,
        sort_keys=True
    )

    return hashlib.sha256(
        fingerprint_string.encode(
            "utf-8"
        )
    ).hexdigest()


# ============================================================
# ALERTMANAGER WEBHOOK
# ============================================================

@app.post("/api/alerts/webhook")
async def alertmanager_webhook(
    request: Request
):

    # --------------------------------------------------------
    # Read JSON
    # --------------------------------------------------------

    try:

        payload = await request.json()

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Invalid JSON payload"
        )

    # --------------------------------------------------------
    # Extract alerts
    # --------------------------------------------------------

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

        # ----------------------------------------------------
        # Process every alert
        # ----------------------------------------------------

        for alert in alerts:

            if not isinstance(
                alert,
                dict
            ):
                continue

            # ------------------------------------------------
            # Labels
            # ------------------------------------------------

            labels = alert.get(
                "labels",
                {}
            )

            if not isinstance(
                labels,
                dict
            ):
                labels = {}

            # ------------------------------------------------
            # Annotations
            # ------------------------------------------------

            annotations = alert.get(
                "annotations",
                {}
            )

            if not isinstance(
                annotations,
                dict
            ):
                annotations = {}

            # ------------------------------------------------
            # Alert name
            # ------------------------------------------------

            alert_name = labels.get(
                "alertname",
                "unknown"
            )

            # ------------------------------------------------
            # Service
            # ------------------------------------------------

            service = labels.get(
                "service"
            )

            if not service:

                service = labels.get(
                    "job"
                )

            if not service:

                service = labels.get(
                    "instance",
                    "unknown"
                )

            # ------------------------------------------------
            # Status
            # ------------------------------------------------

            status = alert.get(
                "status"
            )

            if not status:

                status = payload.get(
                    "status",
                    "unknown"
                )

            # ------------------------------------------------
            # Severity
            # ------------------------------------------------

            severity = labels.get(
                "severity",
                "unknown"
            )

            # ------------------------------------------------
            # Timestamps
            # ------------------------------------------------

            starts_at = alert.get(
                "startsAt"
            )

            ends_at = alert.get(
                "endsAt"
            )

            # ------------------------------------------------
            # Summary
            # ------------------------------------------------

            summary = annotations.get(
                "summary",
                ""
            )

            # ------------------------------------------------
            # Description
            # ------------------------------------------------

            description = annotations.get(
                "description",
                ""
            )

            # ------------------------------------------------
            # Fingerprint
            # ------------------------------------------------

            fingerprint = alert.get(
                "fingerprint"
            )

            # If Alertmanager didn't provide one,
            # generate our own stable fingerprint.
            if not fingerprint:

                fingerprint = generate_fingerprint(
                    alert_name,
                    labels
                )

            # ------------------------------------------------
            # Check whether alert already exists
            # ------------------------------------------------

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

            existing_alert = cursor.fetchone()

            # =================================================
            # EXISTING ALERT
            # =================================================

            if existing_alert:

                alert_id = existing_alert[0]

                # ---------------------------------------------
                # Update existing alert
                # ---------------------------------------------

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
                        received_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id;
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

                updated_id = cursor.fetchone()[0]

                stored_alerts.append(
                    {
                        "id": updated_id,
                        "fingerprint": fingerprint,
                        "alert_name": alert_name,
                        "status": status,
                        "service": service,
                        "severity": severity,
                        "action": "updated"
                    }
                )

            # =================================================
            # NEW ALERT
            # =================================================

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

                stored_alerts.append(
                    {
                        "id": alert_id,
                        "fingerprint": fingerprint,
                        "alert_name": alert_name,
                        "status": status,
                        "service": service,
                        "severity": severity,
                        "action": "created"
                    }
                )

        # ----------------------------------------------------
        # Commit transaction
        # ----------------------------------------------------

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

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return {
        "status": "success",
        "message": "Alertmanager payload received",
        "alerts_received": len(alerts),
        "alerts_stored": stored_alerts
    }


# ============================================================
# GET ALL STORED ALERTS
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
# START SERVER
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )