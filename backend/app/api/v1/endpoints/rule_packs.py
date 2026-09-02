"""Rule-packs endpoints — implemented in RULE-05/RULE-06."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
async def ping():
    return {"message": "rule-packs router placeholder — implement in RULE-05/06"}
