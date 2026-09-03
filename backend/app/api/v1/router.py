"""API v1 router — registers all endpoint modules."""

from fastapi import APIRouter

from app.api.v1.endpoints import analytics, auth, batches, bhashini, inspections, rule_packs, self_check, sso

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(sso.router, prefix="/auth/sso", tags=["sso"])
api_router.include_router(inspections.router, prefix="/inspections", tags=["inspections"])
api_router.include_router(rule_packs.router, prefix="/rule-packs", tags=["rule-packs"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(bhashini.router, prefix="/bhashini", tags=["bhashini"])
api_router.include_router(batches.router, prefix="/batches", tags=["batches"])
api_router.include_router(self_check.router, prefix="/self-check", tags=["self-check"])
