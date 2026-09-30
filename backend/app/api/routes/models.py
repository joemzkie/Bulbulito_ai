from fastapi import APIRouter
from app.providers.registry import list_available_models

router = APIRouter()


@router.get("/models")
def get_models() -> dict:
    return list_available_models()
