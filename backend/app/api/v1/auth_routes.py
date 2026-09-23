from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.persistent_schemas import LoginRequest, RegisterRequest, TokenResponse
from app.core.database import get_db
from app.core.security import issue_token, password_hash
from app.infrastructure.models import Organization, User

router = APIRouter(prefix="/auth", tags=["authentication"])


def _token(user: User) -> TokenResponse:
    from app.core.config import settings

    return TokenResponse(
        access_token=issue_token(user), expires_in=settings.token_expire_minutes * 60
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    organization = Organization(name=request.organization_name.strip())
    db.add(organization)
    db.flush()
    user = User(
        organization_id=organization.id,
        email=str(request.email).lower(),
        password_hash=password_hash.hash(request.password),
        role="owner",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Account could not be created with these details."
        ) from None
    db.refresh(user)
    return _token(user)


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == str(request.email).lower()))
    if (
        user is None
        or not user.is_active
        or not password_hash.verify(request.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=401,
            detail="Email or password is incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _token(user)
