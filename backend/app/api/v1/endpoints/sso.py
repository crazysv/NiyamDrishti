from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import create_access_token, create_refresh_token
from app.schemas.sso import (
    SSOAuthResponse,
    SSOCallbackRequest,
    SSOInitResponse,
    SSOSandboxAuthorizeRequest,
    SSOSandboxProfile,
    SSOStatusResponse,
)
from app.schemas.user import UserRead
from app.services.auth.sso import JanParichaySSOService

router = APIRouter()


@router.get("/status", response_model=SSOStatusResponse)
async def get_sso_status() -> Any:
    """
    Returns the operational configuration and mode of the Government SSO gateway.
    """
    is_live = JanParichaySSOService.is_live_mode()
    return SSOStatusResponse(
        enabled=True,
        mode="live" if is_live else "sandbox",
        provider_name="MeriPehchan (Jan Parichay) NSSO",
        discovery_url=settings.MERIPEHCHAN_DISCOVERY_URL,
        client_id_configured=bool(settings.MERIPEHCHAN_CLIENT_ID),
    )


@router.get("/init", response_model=SSOInitResponse)
@limiter.limit("15/minute")
async def initiate_sso_login(
    request: Request,
    redirect_uri: str | None = Query(None, description="Client redirect URI"),
) -> Any:
    """
    Initiates OIDC login handoff, generating CSRF state and PKCE challenge.
    In production with NIC credentials, returns the live MeriPehchan authorization URL.
    In local dev / evaluation mode, returns the built-in sandbox authorization route.
    """
    auth_url, state, code_verifier, is_sandbox = JanParichaySSOService.initiate_sso(redirect_uri)
    return SSOInitResponse(
        authorization_url=auth_url,
        state=state,
        code_verifier=code_verifier,
        code_challenge=code_verifier,
        is_sandbox=is_sandbox,
    )


@router.get("/sandbox", response_model=list[SSOSandboxProfile])
async def list_sandbox_personas() -> Any:
    """
    Returns available government personas for testing the Jan Parichay authorization handoff.
    """
    return JanParichaySSOService.get_sandbox_personas()


@router.post("/sandbox/authorize")
@limiter.limit("20/minute")
async def authorize_sandbox_persona(
    request: Request,
    payload: SSOSandboxAuthorizeRequest,
) -> Any:
    """
    Simulates successful authentication by an officer in the Jan Parichay gateway,
    issuing a valid authorization code for token exchange.
    """
    try:
        code = JanParichaySSOService.create_sandbox_code(payload.persona_id, payload.state)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {
        "code": code,
        "state": payload.state,
        "message": "Sandbox authorization granted. Return code to /auth/sso/callback.",
    }


@router.post("/callback", response_model=SSOAuthResponse)
@limiter.limit("10/minute")
async def handle_sso_callback(
    request: Request,
    payload: SSOCallbackRequest,
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Receives authorization code from MeriPehchan, performs token exchange,
    verifies government claims, provisions/syncs the user record, and issues application JWTs.
    """
    try:
        claims = await JanParichaySSOService.exchange_code(
            code=payload.code,
            state=payload.state,
            code_verifier=payload.code_verifier,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    user = await JanParichaySSOService.sync_or_create_user(db=db, claims=claims)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Government officer account has been deactivated by administration.",
        )

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    return SSOAuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserRead.model_validate(user),
        claims=claims,
    )
