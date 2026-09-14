import os

import psycopg2
from neo4j import GraphDatabase


POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "rca_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.getenv("POSTGRES_DB", "rca_db")

NEO4J_HOST = os.getenv("NEO4J_HOST", "localhost")
NEO4J_PORT = int(os.getenv("NEO4J_PORT", "7687"))
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

NEO4J_URI = f"bolt://{NEO4J_HOST}:{NEO4J_PORT}"


def fetch_historical_incidents():
    connection = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        dbname=POSTGRES_DB,
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
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
            )

            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        connection.close()


def create_constraints(session):
    queries = [
        """
        CREATE CONSTRAINT incident_id_unique IF NOT EXISTS
        FOR (n:Incident)
        REQUIRE n.incident_id IS UNIQUE
        """,
        """
        CREATE CONSTRAINT service_id_unique IF NOT EXISTS
        FOR (n:Service)
        REQUIRE n.service_id IS UNIQUE
        """,
        """
        CREATE CONSTRAINT root_cause_id_unique IF NOT EXISTS
        FOR (n:RootCause)
        REQUIRE n.root_cause_id IS UNIQUE
        """,
    ]

    for query in queries:
        session.run(query)


def store_incident(tx, incident):
    incident_id = str(incident["incident_id"])
    service = str(incident.get("service") or "")
    root_cause = str(incident.get("root_cause") or "")

    title = str(
        incident.get("alert_name")
        or incident.get("summary")
        or incident_id
    )

    description = str(
        incident.get("description")
        or incident.get("summary")
        or ""
    )

    severity = str(incident.get("severity") or "")
    status = str(incident.get("status") or "")
    timestamp = str(incident.get("started_at") or "")

    tx.run(
        """
        MERGE (i:Incident {incident_id: $incident_id})
        SET
            i.title = $title,
            i.description = $description,
            i.severity = $severity,
            i.timestamp = $timestamp,
            i.status = $status

        MERGE (s:Service {service_id: $service_id})
        SET
            s.name = $service_name,
            s.description = $service_description

        MERGE (i)-[:AFFECTS]->(s)

        WITH i, $root_cause AS root_cause_text
        WHERE root_cause_text <> ""

        MERGE (r:RootCause {root_cause_id: $root_cause_id})
        SET
            r.description = root_cause_text,
            r.category = "historical",
            r.confidence = 1.0

        MERGE (r)-[:CAUSES]->(i)
        MERGE (i)-[:RESOLVED_BY]->(r)
        """,
        incident_id=incident_id,
        title=title,
        description=description,
        severity=severity,
        timestamp=timestamp,
        status=status,
        service_id=f"service:{service}",
        service_name=service,
        service_description=f"Service involved in incident {incident_id}",
        root_cause_id=f"root-cause:{root_cause}",
        root_cause=root_cause,
    )


def populate_graph(incidents):
    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD),
    )

    try:
        driver.verify_connectivity()

        with driver.session() as session:
            create_constraints(session)

            for incident in incidents:
                session.execute_write(store_incident, incident)

    finally:
        driver.close()


def main():
    print("=" * 60)
    print("NEO4J HISTORICAL INCIDENT GRAPH BUILD")
    print("=" * 60)

    incidents = fetch_historical_incidents()

    print(f"Historical incidents found: {len(incidents)}")

    populate_graph(incidents)

    print()
    print("=" * 60)
    print("GRAPH BUILD COMPLETE")
    print("=" * 60)
    print(f"Successfully processed: {len(incidents)}")


if __name__ == "__main__":
    main()