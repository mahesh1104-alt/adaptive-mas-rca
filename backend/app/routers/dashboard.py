from fastapi import APIRouter
from app.models.responses import StatusResponse

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"]
)


@router.get("/", response_model=StatusResponse)
def dashboard_status():
    return {
        "status": "success",
        "message": "Dashboard router is working"
    }