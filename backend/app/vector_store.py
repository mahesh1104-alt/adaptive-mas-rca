from pathlib import Path

import chromadb


# ============================================================
# CHROMA CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

CHROMA_PATH = BASE_DIR / "chroma_data"

COLLECTION_NAME = "rca_embeddings_v1"


# ============================================================
# CHROMA CLIENT
# ============================================================

client = chromadb.PersistentClient(
    path=str(CHROMA_PATH)
)


# ============================================================
# COLLECTION
# ============================================================

collection = client.get_or_create_collection(
    name=COLLECTION_NAME
)


# ============================================================
# STORE EMBEDDING
# ============================================================

def store_embedding(
    incident_id: str,
    embedding: list[float],
    document: str,
    metadata: dict | None = None,
) -> None:
    """
    Store an incident embedding in ChromaDB.
    """

    if not isinstance(incident_id, str):
        raise TypeError(
            "incident_id must be a string"
        )

    if not incident_id.strip():
        raise ValueError(
            "incident_id cannot be empty"
        )

    if not embedding:
        raise ValueError(
            "embedding cannot be empty"
        )

    if not isinstance(document, str):
        raise TypeError(
            "document must be a string"
        )

    collection.upsert(
        ids=[incident_id],
        embeddings=[embedding],
        documents=[document],
        metadatas=[metadata or {}],
    )


# ============================================================
# STORE HISTORICAL INCIDENT
# ============================================================

def store_historical_incident(
    incident: dict,
    embedding: list[float],
    document: str,
) -> None:
    """
    Store a historical incident embedding in ChromaDB.

    The incident's problem description is stored as the
    searchable document, while root cause and resolution
    are stored as metadata.
    """

    if not isinstance(incident, dict):
        raise TypeError(
            "incident must be a dictionary"
        )

    incident_id = incident.get(
        "incident_id"
    )

    if not incident_id:
        raise ValueError(
            "incident must contain incident_id"
        )

    metadata = {
        "alert_name": str(
            incident.get("alert_name", "")
        ),

        "service": str(
            incident.get("service", "")
        ),

        "severity": str(
            incident.get("severity", "")
        ),

        "status": str(
            incident.get("status", "")
        ),

        "started_at": str(
            incident.get("started_at", "")
        ),

        "resolved_at": str(
            incident.get("resolved_at", "")
        ),

        "root_cause": str(
            incident.get("root_cause", "")
        ),

        "resolution": str(
            incident.get("resolution", "")
        ),
    }

    store_embedding(
        incident_id=str(incident_id),
        embedding=embedding,
        document=document,
        metadata=metadata,
    )



# ============================================================
# SEARCH SIMILAR INCIDENTS
# ============================================================

def search_similar_incidents(
    embedding: list[float],
    n_results: int = 5,
) -> dict:
    """
    Search ChromaDB for incidents with similar embeddings.
    """

    if not embedding:
        raise ValueError(
            "embedding cannot be empty"
        )

    if n_results < 1:
        raise ValueError(
            "n_results must be at least 1"
        )

    return collection.query(
        query_embeddings=[embedding],
        n_results=n_results,
    )


# ============================================================
# COLLECTION SIZE
# ============================================================

def get_collection_count() -> int:
    """
    Return the number of stored incident embeddings.
    """

    return collection.count()

def delete_embeddings(incident_ids: list[str]) -> None:
    """
    Delete specific incident embeddings from ChromaDB.
    """
    if not incident_ids:
        raise ValueError("incident_ids cannot be empty")

    collection.delete(ids=incident_ids)
# ============================================================
# MANUAL TEST
# ============================================================

if __name__ == "__main__":

    from embedding_generation import (
        generate_historical_incident_embedding,
        historical_incident_to_text,
    )


    historical_incident = {

        "incident_id": "INC-HIST-001",

        "alert_name": "DatabaseConnectionFailure",

        "service": "inventory-service",

        "severity": "HIGH",

        "status": "resolved",

        "started_at": "2026-09-01 10:00:00",

        "resolved_at": "2026-09-01 10:30:00",

        "summary": (
            "Inventory service database connection failed"
        ),

        "description": (
            "PostgreSQL connections timed out "
            "during inventory updates."
        ),

        "root_cause": (
            "Database connection pool exhausted"
        ),

        "resolution": (
            "Increased database connection pool size"
        ),
    }


    # --------------------------------------------------------
    # GENERATE DOCUMENT
    # --------------------------------------------------------

    document = historical_incident_to_text(
        historical_incident
    )

    print()
    print("=" * 60)
    print("HISTORICAL INCIDENT DOCUMENT")
    print("=" * 60)
    print(document)
    print("=" * 60)


    # --------------------------------------------------------
    # GENERATE EMBEDDING
    # --------------------------------------------------------

    embedding = (
        generate_historical_incident_embedding(
            historical_incident
        )
    )

    print()
    print(
        "Embedding dimension:",
        len(embedding)
    )


    # --------------------------------------------------------
    # STORE INCIDENT
    # --------------------------------------------------------

    store_historical_incident(
        incident=historical_incident,
        embedding=embedding,
        document=document,
    )

    print(
        "Historical incident stored:",
        historical_incident["incident_id"]
    )

    print(
        "Total stored incidents:",
        get_collection_count()
    )


    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    results = search_similar_incidents(
        embedding=embedding,
        n_results=1,
    )

    print()
    print("=" * 60)
    print("SIMILAR INCIDENT SEARCH")
    print("=" * 60)

    print(
        "IDs:",
        results["ids"]
    )

    print(
        "Documents:",
        results["documents"]
    )

    print(
        "Metadata:",
        results["metadatas"]
    )

    print(
        "Distances:",
        results["distances"]
    )

    print("=" * 60)