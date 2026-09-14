import os

from neo4j import GraphDatabase

from .build_neo4j_graph import create_constraints, store_incident
from .embedding_generation import (
    generate_historical_incident_embedding,
    historical_incident_to_text,
)
from .vector_store import store_historical_incident


NEO4J_HOST = os.getenv("NEO4J_HOST", "localhost")
NEO4J_PORT = int(os.getenv("NEO4J_PORT", "7687"))
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

NEO4J_URI = f"bolt://{NEO4J_HOST}:{NEO4J_PORT}"


def add_resolved_incident(incident: dict) -> dict:
    """
    Add one newly resolved incident to ChromaDB and Neo4j.

    Returns a summary of the knowledge-base update.
    """
    if not isinstance(incident, dict):
        raise TypeError("incident must be a dictionary")

    incident_id = incident.get("incident_id")

    if not incident_id:
        raise ValueError(
            "incident must contain incident_id"
        )

    if not incident.get("root_cause"):
        raise ValueError(
            "incident must contain root_cause"
        )

    document = historical_incident_to_text(
        incident
    )

    embedding = generate_historical_incident_embedding(
        incident
    )

    store_historical_incident(
        incident=incident,
        embedding=embedding,
        document=document,
    )

    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(
            NEO4J_USER,
            NEO4J_PASSWORD,
        ),
    )

    try:
        driver.verify_connectivity()

        with driver.session() as session:
            create_constraints(session)

            session.execute_write(
                store_incident,
                incident,
            )
    finally:
        driver.close()

    return {
        "incident_id": str(incident_id),
        "chroma_updated": True,
        "neo4j_updated": True,
        "document": document,
    }