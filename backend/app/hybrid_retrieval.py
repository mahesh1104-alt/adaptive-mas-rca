import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

from .embedding_generation import generate_incident_embedding
from .vector_store import search_similar_incidents


VECTOR_TOP_K = 10
GRAPH_MAX_HOPS = 2
VECTOR_WEIGHT = 0.70
GRAPH_WEIGHT = 0.30


NEO4J_HOST = os.getenv("NEO4J_HOST", "localhost")
NEO4J_PORT = int(os.getenv("NEO4J_PORT", "7687"))
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

NEO4J_URI = f"bolt://{NEO4J_HOST}:{NEO4J_PORT}"


def _normalize_vector_distance(distance: float) -> float:
    """
    Convert a ChromaDB distance into a bounded relevance score.

    Smaller distance means greater similarity.
    The resulting score is in the range (0, 1].
    """
    if distance < 0:
        distance = 0

    return 1.0 / (1.0 + distance)


def _query_graph(driver, service_names: list[str]) -> list[dict]:
    """
    Retrieve two-hop graph evidence starting from Service nodes.

    Service <- Incident -> RootCause
    """
    if not service_names:
        return []

    query = """
    MATCH (s:Service)<-[:AFFECTS]-(i:Incident)<-[:CAUSES]-(r:RootCause)
    WHERE s.name IN $service_names
    RETURN
        s.name AS service,
        i.incident_id AS incident_id,
        i.title AS incident_title,
        r.root_cause_id AS root_cause_id,
        r.description AS root_cause,
        2 AS hop_count
    ORDER BY i.incident_id ASC
    """

    with driver.session() as session:
        result = session.run(
            query,
            service_names=service_names,
        )
        return [record.data() for record in result]


def _merge_results(
    vector_results: list[dict],
    graph_results: list[dict],
) -> list[dict]:
    """
    Merge vector and graph evidence by incident ID and rank by
    weighted relevance.
    """
    merged = {}

    for item in vector_results:
        incident_id = item["incident_id"]

        merged[incident_id] = {
            "incident_id": incident_id,
            "service": item.get("service", ""),
            "title": item.get("title", ""),
            "document": item.get("document", ""),
            "vector_distance": item.get("distance"),
            "vector_score": item.get("vector_score", 0.0),
            "graph_score": 0.0,
            "graph_evidence": [],
        }

    for item in graph_results:
        incident_id = item["incident_id"]

        if incident_id not in merged:
            merged[incident_id] = {
                "incident_id": incident_id,
                "service": item.get("service", ""),
                "title": item.get("incident_title", ""),
                "document": "",
                "vector_distance": None,
                "vector_score": 0.0,
                "graph_score": 0.0,
                "graph_evidence": [],
            }

        merged[incident_id]["graph_score"] = max(
            merged[incident_id]["graph_score"],
            1.0 if item.get("hop_count") == GRAPH_MAX_HOPS else 0.5,
        )

        merged[incident_id]["graph_evidence"].append(
            {
                "service": item.get("service", ""),
                "root_cause_id": item.get("root_cause_id"),
                "root_cause": item.get("root_cause", ""),
                "hop_count": item.get("hop_count"),
            }
        )

    for result in merged.values():
        result["relevance_score"] = (
            VECTOR_WEIGHT * result["vector_score"]
            + GRAPH_WEIGHT * result["graph_score"]
        )

    return sorted(
        merged.values(),
        key=lambda item: item["relevance_score"],
        reverse=True,
    )


def retrieval(query: str, top_k: int = VECTOR_TOP_K) -> list[dict]:
    """
    Execute hybrid vector + graph retrieval for a single query.

    Returns combined evidence ranked by relevance.
    """
    if not isinstance(query, str):
        raise TypeError("query must be a string")

    if not query.strip():
        raise ValueError("query cannot be empty")

    if top_k < 1:
        raise ValueError("top_k must be at least 1")

    query_embedding = generate_incident_embedding(
        {
            "incident_id": "HYBRID-QUERY",
            "features": {
                "logs": [
                    {
                        "level": "ERROR",
                        "template": query,
                    }
                ],
                "metrics": [],
                "traces": [],
                "source": [],
            },
        }
    )

    chroma_results = search_similar_incidents(
        embedding=query_embedding,
        n_results=top_k,
    )

    ids = chroma_results.get("ids", [[]])[0]
    distances = chroma_results.get("distances", [[]])[0]
    documents = chroma_results.get("documents", [[]])[0]
    metadatas = chroma_results.get("metadatas", [[]])[0]

    vector_results = []

    for index, incident_id in enumerate(ids):
        metadata = metadatas[index] if index < len(metadatas) else {}
        distance = distances[index] if index < len(distances) else 0.0
        document = documents[index] if index < len(documents) else ""

        vector_results.append(
            {
                "incident_id": incident_id,
                "service": metadata.get("service", ""),
                "title": metadata.get("alert_name", ""),
                "document": document,
                "distance": distance,
                "vector_score": _normalize_vector_distance(distance),
            }
        )

    service_names = sorted(
        {
            item["service"]
            for item in vector_results
            if item.get("service")
        }
    )

    graph_results = []

    if service_names:
        driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD),
        )

        try:
            driver.verify_connectivity()
            graph_results = _query_graph(
                driver,
                service_names,
            )
        finally:
            driver.close()

    return _merge_results(
        vector_results=vector_results,
        graph_results=graph_results,
    )