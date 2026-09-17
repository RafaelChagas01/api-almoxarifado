from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit
from app.db import get_db
from app.models import AuditLog, User
from app.schemas import AuditOut, UserCreate, UserOut, UserUpdate
from app.security import Admin, hash_password

router = APIRouter(tags=["admin"])

Db = Annotated[Session, Depends(get_db)]


@router.get("/users", response_model=list[UserOut], summary="List users")
def list_users(db: Db, _: Admin):
    return db.scalars(select(User).order_by(User.name)).all()


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED, summary="Create user")
def create_user(data: UserCreate, db: Db, admin: Admin):
    user = User(email=data.email.lower(), name=data.name, role=data.role, password_hash=hash_password(data.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from None
    audit.record(db, admin, "user.create", "user", user.id, role=user.role.value)
    db.commit()
    return user


@router.patch("/users/{user_id}", response_model=UserOut, summary="Change role or deactivate user")
def update_user(user_id: int, data: UserUpdate, db: Db, admin: Admin):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot change your own role or status")

    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(user, field, value)
    audit.record(db, admin, "user.update", "user", user.id, **{k: (v.value if hasattr(v, "value") else v) for k, v in changes.items()})
    db.commit()
    return user


@router.get("/audit-logs", response_model=list[AuditOut], summary="Audit trail")
def audit_logs(
    db: Db,
    _: Admin,
    entity: Annotated[str | None, Query(pattern=r"^(product|user)$")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    query = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)
    if entity:
        query = query.where(AuditLog.entity == entity)
    return db.scalars(query).all()
