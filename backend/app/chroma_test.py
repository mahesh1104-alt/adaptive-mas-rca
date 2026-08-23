import chromadb
from pathlib import Path


# Persistent ChromaDB storage
BASE_DIR = Path(__file__).resolve().parent.parent
CHROMA_PATH = BASE_DIR / "chroma_data"

client = chromadb.PersistentClient(path=str(CHROMA_PATH))

# Create or retrieve collection
collection = client.get_or_create_collection(
    name="rca_embeddings"
)

# Small test embeddings
documents = [
    "Database connection timeout",
    "PostgreSQL connection failed",
    "Frontend login page is slow",
]

embeddings = [
    [1.0, 0.0, 0.0],
    [0.9, 0.1, 0.0],
    [0.0, 1.0, 0.0],
]

ids = [
    "incident-001",
    "incident-002",
    "incident-003",
]

# Insert test embeddings
collection.upsert(
    ids=ids,
    embeddings=embeddings,
    documents=documents,
)

print("Collection:", collection.name)
print("Total records:", collection.count())

# Query for a database-related incident
results = collection.query(
    query_embeddings=[[0.95, 0.05, 0.0]],
    n_results=1,
)

print("\nNearest match:")
print(results["documents"][0][0])
print("ID:", results["ids"][0][0])