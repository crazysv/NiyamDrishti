import base64
import hashlib
import logging
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.base import User
from app.schemas.sso import JanParichayClaims, SSOSandboxProfile

logger = logging.getLogger("niyamdrishti.sso")

# Predefined mock government personas for Sandbox / Evaluation mode
SANDBOX_PERSONAS: dict[str, dict[str, Any]] = {
    "officer_suresh": {
        "parichay_id": "PARICHAY-DL-LM-1049",
        "user_id": "gov_officer_suresh",
        "full_name": "Suresh Sharma",
        "email": "suresh.sharma@gov.in",
        "department": "Legal Metrology Department (DoCA)",
        "designation": "Legal Metrology Inspector",
        "state_code": "DL",
        "service_id": "LM-NSSO-01",
        "mapped_app_role": "officer",
        "description": "Field Officer authorized to conduct marketplace inspections and package seizures in Delhi NCT.",
    },
    "supervisor_priya": {
        "parichay_id": "PARICHAY-MH-LM-0812",
        "user_id": "gov_sup_priya",
        "full_name": "Priya Verma",
        "email": "priya.verma@nic.in",
        "department": "Directorate of Legal Metrology, Maharashtra",
        "designation": "Deputy Controller of Legal Metrology",
        "state_code": "MH",
        "service_id": "LM-NSSO-02",
        "mapped_app_role": "supervisor",
        "description": "Zonal Supervisory Officer monitoring compliance hotspots and reviewing flagged inspections.",
    },
    "admin_rajesh": {
        "parichay_id": "PARICHAY-HQ-DOCA-0001",
        "user_id": "gov_admin_rajesh",
        "full_name": "Rajesh Gupta",
        "email": "rajesh.gupta@gov.in",
        "department": "Ministry of Consumer Affairs, Food & Public Distribution",
        "designation": "Director & National Administrator",
        "state_code": "DL",
        "service_id": "LM-NSSO-00",
        "mapped_app_role": "admin",
        "description": "Central Departmental Administrator with authority to publish statutory rule packs and audit logs.",
    },
}

# Temporary in-memory code store for sandbox mode (code -> (persona_id, state, expires_at))
_SANDBOX_CODES: dict[str, tuple[str, str, float]] = {}


def _generate_pkce_challenge(verifier: str) -> str:
    """Computes base64url-encoded SHA-256 code challenge for PKCE."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


class JanParichaySSOService:
    """
    Dual-Mode Government Single Sign-On Adapter (E4-01, ADR-016).
    Supports live NIC MeriPehchan / Jan Parichay OIDC when configured,
    with an automatic, high-fidelity developer/hackathon sandbox fallback.
    """

    @classmethod
    def is_live_mode(cls) -> bool:
        """
        Returns True only if live NIC client credentials are configured.
        """
        cid = (settings.MERIPEHCHAN_CLIENT_ID or "").strip()
        secret = (settings.MERIPEHCHAN_CLIENT_SECRET or "").strip()
        return bool(cid and secret and cid != "mock-client-id" and secret != "mock-secret")

    @classmethod
    def initiate_sso(cls, redirect_uri: str | None = None) -> tuple[str, str, str, bool]:
        """
        Initiates the SSO flow, generating CSRF state and PKCE challenge.
        Returns: (authorization_url, state, code_verifier, is_sandbox)
        """
        state = secrets.token_urlsafe(24)
        code_verifier = secrets.token_urlsafe(32)
        code_challenge = _generate_pkce_challenge(code_verifier)
        target_redirect = redirect_uri or settings.MERIPEHCHAN_REDIRECT_URI

        if cls.is_live_mode():
            # Build standard OIDC Authorization Code request for live MeriPehchan
            params = {
                "client_id": settings.MERIPEHCHAN_CLIENT_ID,
                "redirect_uri": target_redirect,
                "response_type": "code",
                "scope": "openid profile email department",
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
            query_str = "&".join(f"{k}={v}" for k, v in params.items())
            auth_url = f"{settings.MERIPEHCHAN_AUTHORIZE_URL}?{query_str}"
            is_sandbox = False
        else:
            # Sandbox route
            auth_url = f"/api/v1/auth/sso/sandbox?state={state}&redirect_uri={target_redirect}"
            is_sandbox = True

        return auth_url, state, code_verifier, is_sandbox

    @classmethod
    def get_sandbox_personas(cls) -> list[SSOSandboxProfile]:
        """Returns the list of available government officer sandbox personas."""
        profiles = []
        for persona_id, data in SANDBOX_PERSONAS.items():
            profiles.append(
                SSOSandboxProfile(
                    id=persona_id,
                    full_name=data["full_name"],
                    email=data["email"],
                    designation=data["designation"],
                    department=data["department"],
                    state_code=data["state_code"],
                    mapped_app_role=data["mapped_app_role"],
                    description=data["description"],
                )
            )
        return profiles

    @classmethod
    def create_sandbox_code(cls, persona_id: str, state: str) -> str:
        """
        Generates and stores a short-lived authorization code for a selected persona.
        """
        if persona_id not in SANDBOX_PERSONAS:
            raise ValueError(f"Unknown sandbox persona: {persona_id}")
        code = f"SANDBOX-JANPARICHAY-{secrets.token_urlsafe(16)}"
        expires_at = time.time() + 300.0  # 5 minutes
        _SANDBOX_CODES[code] = (persona_id, state, expires_at)
        return code

    @classmethod
    async def exchange_code(
        cls,
        code: str,
        state: str,
        code_verifier: str | None = None,
        redirect_uri: str | None = None,
    ) -> JanParichayClaims:
        """
        Exchanges authorization code for verified government claims.
        Handles both sandbox mock resolution and live OIDC token endpoint calls.
        """
        if cls.is_live_mode():
            target_redirect = redirect_uri or settings.MERIPEHCHAN_REDIRECT_URI
            token_payload = {
                "grant_type": "authorization_code",
                "client_id": settings.MERIPEHCHAN_CLIENT_ID,
                "client_secret": settings.MERIPEHCHAN_CLIENT_SECRET,
                "code": code,
                "redirect_uri": target_redirect,
            }
            if code_verifier:
                token_payload["code_verifier"] = code_verifier

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(settings.MERIPEHCHAN_TOKEN_URL, data=token_payload)
                if resp.status_code != 200:
                    logger.error(f"MeriPehchan token exchange failed: {resp.status_code} {resp.text}")
                    raise ValueError("Failed to exchange authorization code with MeriPehchan gateway.")
                token_data = resp.json()

                # Call userinfo endpoint with bearer token
                access_token = token_data.get("access_token")
                userinfo_resp = await client.get(
                    settings.MERIPEHCHAN_USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if userinfo_resp.status_code != 200:
                    logger.error(f"MeriPehchan userinfo failed: {userinfo_resp.status_code} {userinfo_resp.text}")
                    raise ValueError("Failed to retrieve government userinfo from MeriPehchan gateway.")
                userinfo = userinfo_resp.json()

                return JanParichayClaims(
                    parichay_id=userinfo.get("parichay_id") or userinfo.get("sub", "UNKNOWN"),
                    user_id=userinfo.get("user_id"),
                    full_name=userinfo.get("name") or userinfo.get("full_name", "Government Officer"),
                    email=userinfo.get("email"),
                    department=userinfo.get("department", "Department of Consumer Affairs"),
                    designation=userinfo.get("designation", "Legal Metrology Officer"),
                    state_code=userinfo.get("state_code"),
                    service_id=userinfo.get("service_id"),
                )
        else:
            # Sandbox verification
            if code not in _SANDBOX_CODES:
                raise ValueError("Invalid or expired sandbox authorization code.")
            persona_id, expected_state, expires_at = _SANDBOX_CODES.pop(code)
            if time.time() > expires_at:
                raise ValueError("Sandbox authorization code has expired.")
            if expected_state != state:
                raise ValueError("CSRF state mismatch in sandbox authorization code exchange.")

            persona_data = SANDBOX_PERSONAS[persona_id]
            return JanParichayClaims(
                parichay_id=persona_data["parichay_id"],
                user_id=persona_data["user_id"],
                full_name=persona_data["full_name"],
                email=persona_data["email"],
                department=persona_data["department"],
                designation=persona_data["designation"],
                state_code=persona_data["state_code"],
                service_id=persona_data["service_id"],
            )

    @classmethod
    def map_claims_to_role(cls, claims: JanParichayClaims) -> str:
        """
        Maps official government designations and ministry departments to application RBAC roles.
        """
        desig = claims.designation.lower()
        dept = claims.department.lower()

        # Admin tier: Central ministry directorate, controllers general, national administrators
        if (
            any(term in desig for term in ["director", "admin", "controller general", "joint secretary"])
            or "ministry" in dept
        ):
            return "admin"

        # Supervisory tier: Zonal / state controllers, deputy controllers, enforcement superintendents
        if any(term in desig for term in ["controller", "deputy controller", "supervisor", "superintendent"]):
            return "supervisor"

        # Default field tier: Legal Metrology Officers and field inspectors
        return "officer"

    @classmethod
    async def sync_or_create_user(cls, db: AsyncSession, claims: JanParichayClaims) -> User:
        """
        Just-In-Time (JIT) provisioning: Locates existing officer account by email
        or automatically provisions a new User record with government credentials.
        """
        stmt = select(User).where(User.email == claims.email)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()

        mapped_role = cls.map_claims_to_role(claims)
        region = claims.state_code or "National"

        if user:
            # Update user profile attributes from government claims
            user.full_name = claims.full_name
            user.region = region
            if mapped_role in ("supervisor", "admin") and user.role == "officer":
                user.role = mapped_role
            await db.commit()
            await db.refresh(user)
            logger.info(f"Synchronized existing government officer identity: {user.email} (Role: {user.role})")
            return user

        # Provision new user
        user = User(
            id=uuid.uuid4(),
            email=claims.email,
            password_hash=get_password_hash(secrets.token_urlsafe(32)),  # Random non-guessable hash for SSO accounts
            full_name=claims.full_name,
            role=mapped_role,
            region=region,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info(
            f"JIT provisioned new government officer account from MeriPehchan: {user.email} (Role: {user.role})"
        )
        return user
