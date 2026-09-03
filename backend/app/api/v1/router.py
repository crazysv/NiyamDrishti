"""API v1 router — registers all endpoint modules."""

from fastapi import APIRouter

from app.api.v1.endpoints import analytics, auth, inspections, rule_packs

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(inspections.router, prefix="/inspections", tags=["inspections"])
api_router.include_router(rule_packs.router, prefix="/rule-packs", tags=["rule-packs"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
