from jose import jwt

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, get_password_hash, verify_password


def test_password_hashing():
    pwd = "supersecretpassword123"
    hashed = get_password_hash(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrongpassword", hashed) is False


def test_jwt_tokens():
    user_id = "123e4567-e89b-12d3-a456-426614174000"
    access_token = create_access_token(user_id)
    payload = jwt.decode(access_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert payload["sub"] == user_id
    assert "exp" in payload

    refresh_token = create_refresh_token(user_id)
    r_payload = jwt.decode(refresh_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert r_payload["sub"] == user_id
    assert r_payload.get("type") == "refresh"
