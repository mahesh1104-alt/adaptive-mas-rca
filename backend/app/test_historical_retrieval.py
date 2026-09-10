from app.embedding_generation import generate_incident_embedding
from app.vector_store import search_similar_incidents


feature_bundle = {
    "incident_id": "RCA-TEST",
    "features": {
        "logs": [
            {
                "level": "ERROR",
                "template": "Database connection attempts are timing out",
            },
            {
                "level": "ERROR",
                "template": "Order service cannot obtain database connections",
            },
        ],
        "metrics": [],
        "traces": [],
        "source": [],
    },
}


embedding = generate_incident_embedding(feature_bundle)

results = search_similar_incidents(
    embedding=embedding,
    n_results=5,
)

print()
print("=" * 60)
print("SEMANTIC HISTORICAL RETRIEVAL TEST")
print("=" * 60)

ids = results.get("ids", [[]])[0]
distances = results.get("distances", [[]])[0]
metadatas = results.get("metadatas", [[]])[0]

for index, incident_id in enumerate(ids):
    metadata = metadatas[index]

    print()
    print(f"Rank: {index + 1}")
    print(f"Incident ID: {incident_id}")
    print(f"Distance: {distances[index]}")
    print(f"Service: {metadata.get('service')}")
    print(f"Alert: {metadata.get('alert_name')}")
    print(f"Severity: {metadata.get('severity')}")
    print(f"Root Cause: {metadata.get('root_cause')}")