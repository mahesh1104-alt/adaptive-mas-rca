from fastapi import FastAPI

app = FastAPI(title="Adaptive MAS RCA API")


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "adaptive-mas-rca-backend"
    }