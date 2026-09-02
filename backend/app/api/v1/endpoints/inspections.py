"""Inspections endpoints — implemented in CAP-08 onwards."""
from fastapi import APIRouter
router = APIRouter()

@router.get("/ping")
async def ping():
    return {"message": "inspections router placeholder — implement in CAP-08"}
