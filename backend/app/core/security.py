import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.infrastructure.models import User

password_hash = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)
_development_secret = secrets.token_urlsafe(48)
_development_redaction_secret = secrets.token_urlsafe(48)


def signing_secret() -> str:
    if settings.jwt_secret:
        return settings.jwt_secret
    if settings.environment.lower() == "production":
        raise RuntimeError("CAUSORA_JWT_SECRET must be configured in production.")
    return _development_secret


def redaction_secret() -> str:
    if settings.redaction_secret:
        return settings.redaction_secret
    if settings.environment.lower() == "production":
        raise RuntimeError("CAUSORA_REDACTION_SECRET must be configured in production.")
    return _development_redaction_secret


def issue_token(user: User) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(user.id),
        "org": str(user.organization_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.token_expire_minutes),
    }
    return jwt.encode(claims, signing_secret(), algorithm="HS256")


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        claims = jwt.decode(credentials.credentials, signing_secret(), algorithms=["HS256"])
        user_id = UUID(claims["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError, RuntimeError):
        raise unauthorized from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user
