import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr

from app.schemas.user import UserRead


class JanParichayClaims(BaseModel):
    """
    Standard claims payload returned by NIC MeriPehchan / Jan Parichay OIDC service.
    """
    parichay_id: str
    user_id: Optional[str] = None
    full_name: str
    email: str
    department: str
    designation: str
    state_code: Optional[str] = None
    service_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SSOSandboxProfile(BaseModel):
    """
    Pre-configured mock government officer persona available in sandbox mode.
    """
    id: str
    full_name: str
    email: str
    designation: str
    department: str
    state_code: str
    mapped_app_role: str
    description: str


class SSOInitResponse(BaseModel):
    """
    Response returned to frontend to initiate government OIDC login flow.
    """
    authorization_url: str
    state: str
    code_verifier: Optional[str] = None
    code_challenge: Optional[str] = None  # Deprecated alias for backward compatibility
    is_sandbox: bool


class SSOCallbackRequest(BaseModel):
    """
    Authorization code payload posted by frontend upon return from MeriPehchan.
    """
    code: str
    state: str
    code_verifier: Optional[str] = None


class SSOSandboxAuthorizeRequest(BaseModel):
    """
    Request to approve authentication as a specific sandbox persona.
    """
    persona_id: str
    state: str


class SSOStatusResponse(BaseModel):
    """
    Health and configuration status of the government SSO gateway.
    """
    enabled: bool
    mode: str  # 'live' or 'sandbox'
    provider_name: str = "MeriPehchan (Jan Parichay) NSSO"
    discovery_url: str
    client_id_configured: bool


class SSOAuthResponse(BaseModel):
    """
    Authentication response with JWT tokens and provisioned officer identity.
    """
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserRead
    claims: Optional[JanParichayClaims] = None
