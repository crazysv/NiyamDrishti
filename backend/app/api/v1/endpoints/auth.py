"""Auth endpoints — implemented in AUTH-02/AUTH-03."""
from fastapi import APIRouter
router = APIRouter()

@router.get("/ping")
async def ping():
    return {"message": "auth router placeholder — implement in AUTH-02/03"}
