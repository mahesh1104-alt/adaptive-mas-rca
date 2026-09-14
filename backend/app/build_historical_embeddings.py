import os

import psycopg2
from psycopg2.extras import RealDictCursor

from .embedding_generation import (
    historical_incident_to_text,
    generate_historical_incident_embedding,
)

from .vector_store import (
    store_historical_incident,
)


# ============================================================
# POSTGRESQL CONFIGURATION
# ============================================================

POSTGRES_HOST = os.getenv(
    "POSTGRES_HOST",
    "postgres",
)

POSTGRES_PORT = int(
    os.getenv(
        "POSTGRES_PORT",
        "5432",
    )
)

POSTGRES_USER = os.getenv(
    "POSTGRES_USER",
    "rca_user",
)

POSTGRES_PASSWORD = os.getenv(
    "POSTGRES_PASSWORD",
    "rca_password",
)

POSTGRES_DB = os.getenv(
    "POSTGRES_DB",
    "rca_db",
)


# ============================================================
# FETCH HISTORICAL INCIDENTS
# ============================================================

def get_all_historical_incidents() -> list[dict]:
    """
    Retrieve all historical incidents from PostgreSQL.
    """

    conn = None
    cursor = None

    try:

        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB,
        )

        cursor = conn.cursor(
            cursor_factory=RealDictCursor
        )

        query = """
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
            ORDER BY started_at ASC
        """

        cursor.execute(query)

        incidents = cursor.fetchall()

        return [
            dict(incident)
            for incident in incidents
        ]

    except Exception as e:

        print(
            f"Historical incident retrieval failed: {e}"
        )

        return []

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# BUILD HISTORICAL EMBEDDING INDEX
# ============================================================

def build_historical_embedding_index() -> int:
    """
    Generate and store embeddings for all historical incidents.

    Returns:
        Number of successfully embedded incidents.
    """

    incidents = get_all_historical_incidents()

    if not incidents:

        print(
            "No historical incidents found."
        )

        return 0

    print()
    print("=" * 60)
    print("HISTORICAL EMBEDDING INDEX")
    print("=" * 60)

    print(
        "Historical incidents found:",
        len(incidents),
    )

    successful = 0

    for index, incident in enumerate(
        incidents,
        start=1,
    ):

        incident_id = incident.get(
            "incident_id",
            "UNKNOWN",
        )

        print()
        print(
            f"[{index}/{len(incidents)}] "
            f"Processing {incident_id}"
        )

        try:

            # ------------------------------------------------
            # Convert incident to searchable text
            # ------------------------------------------------

            document = historical_incident_to_text(
                incident
            )

            # ------------------------------------------------
            # Generate 384-dimensional embedding
            # ------------------------------------------------

            embedding = (
                generate_historical_incident_embedding(
                    incident
                )
            )

            # ------------------------------------------------
            # Store in ChromaDB
            # ------------------------------------------------

            store_historical_incident(
                incident=incident,
                embedding=embedding,
                document=document,
            )

            print(
                f"Stored {incident_id}"
            )

            successful += 1

        except Exception as e:

            print(
                f"Failed to process "
                f"{incident_id}: {e}"
            )

    print()
    print("=" * 60)
    print("INDEX BUILD COMPLETE")
    print("=" * 60)

    print(
        "Successfully embedded:",
        successful,
    )

    print(
        "Failed:",
        len(incidents) - successful,
    )

    return successful


# ============================================================
# MANUAL TEST
# ============================================================

if __name__ == "__main__":

    build_historical_embedding_index()