from app.embedding_generation import (
    generate_embedding,
)

from app.vector_store import (
    search_similar_incidents,
)


# ============================================================
# CURRENT INCIDENT
# ============================================================

current_incident_text = """
Order service is experiencing database connectivity problems.
Requests are failing because the application cannot obtain
available database connections. Database connection attempts
are timing out under load.
"""


# ============================================================
# GENERATE EMBEDDING
# ============================================================

embedding = generate_embedding(
    current_incident_text
)


print()
print("=" * 60)
print("CURRENT INCIDENT")
print("=" * 60)

print(current_incident_text.strip())

print()
print(
    "Embedding dimension:",
    len(embedding)
)


# ============================================================
# SIMILARITY SEARCH
# ============================================================

results = search_similar_incidents(
    embedding=embedding,
    n_results=5,
)


print()
print("=" * 60)
print("SIMILAR HISTORICAL INCIDENTS")
print("=" * 60)


for index in range(
    len(results["ids"][0])
):

    incident_id = results["ids"][0][index]

    document = results["documents"][0][index]

    metadata = results["metadatas"][0][index]

    distance = results["distances"][0][index]

    print()
    print(
        f"Rank: {index + 1}"
    )

    print(
        f"Incident ID: {incident_id}"
    )

    print(
        f"Distance: {distance}"
    )

    print(
        f"Service: {metadata.get('service')}"
    )

    print(
        f"Severity: {metadata.get('severity')}"
    )

    print(
        f"Alert: {metadata.get('alert_name')}"
    )

    print(
        f"Root Cause: {metadata.get('root_cause')}"
    )

    print(
        f"Resolution: {metadata.get('resolution')}"
    )

    print(
        f"Document: {document}"
    )


print()
print("=" * 60)