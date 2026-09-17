from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.config import get_settings
from app.db import get_db
from app.models import User
from app.ratelimit import LoginLimiter
from app.schemas import Token, UserOut
from app.security import CurrentUser, create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

settings = get_settings()
limiter = LoginLimiter(settings.login_attempts, settings.login_window_seconds)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


@router.post("/token", response_model=Token, summary="Log in with email and password")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], request: Request, db: Annotated[Session, Depends(get_db)]):
    email = form.username.strip().lower()[:120]
    key = f"{client_ip(request)}:{email}"

    if limiter.blocked(key):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts. Try again in a few minutes.")

    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    valid = verify_password(form.password[:128], user.password_hash if user else None)

    if not valid or user is None or not user.is_active:
        limiter.fail(key)
        audit.record(db, None, "auth.login_failed", "user", user.id if user else None, email=email)
        db.commit()
        # mesma mensagem pra email inexistente, senha errada ou usuario inativo
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    limiter.reset(key)
    token, expires = create_access_token(user)
    return Token(access_token=token, expires_in=expires)


@router.get("/me", response_model=UserOut, summary="Current user")
def me(user: CurrentUser):
    return user
