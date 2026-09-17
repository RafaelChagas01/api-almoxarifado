from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Role, User

password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# hash fixo pra gastar o mesmo tempo quando o email nao existe
_DUMMY_HASH = password_hash.hash("senha-que-nao-existe-em-lugar-nenhum")

ROLE_LEVEL = {Role.viewer: 0, Role.operator: 1, Role.admin: 2}


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    return password_hash.verify(password, hashed or _DUMMY_HASH) and hashed is not None


def create_access_token(user: User) -> tuple[str, int]:
    settings = get_settings()
    expires = settings.access_token_minutes * 60
    now = datetime.now(UTC)
    payload = {"sub": str(user.id), "iat": now, "exp": now + timedelta(seconds=expires)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256"), expires


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Annotated[Session, Depends(get_db)]) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"], options={"require": ["exp", "sub"]})
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError):
        raise unauthorized from None

    # papel e status vem do banco a cada request: desativar um usuario vale na hora
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require_role(minimum: Role):
    def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if ROLE_LEVEL[user.role] < ROLE_LEVEL[minimum]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your role does not allow this action")
        return user

    return checker


CurrentUser = Annotated[User, Depends(get_current_user)]
Operator = Annotated[User, Depends(require_role(Role.operator))]
Admin = Annotated[User, Depends(require_role(Role.admin))]
