from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit
from app.db import get_db
from app.models import Movement, Product
from app.schemas import MovementCreate, MovementOut, ProductCreate, ProductOut, ProductPage, ProductUpdate
from app.security import Admin, CurrentUser, Operator
from app.stock import StockError, register_movement

router = APIRouter(prefix="/products", tags=["products"])

Db = Annotated[Session, Depends(get_db)]


def get_product_or_404(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.get("", response_model=ProductPage, summary="List products")
def list_products(
    db: Db,
    _: CurrentUser,
    search: Annotated[str | None, Query(max_length=60)] = None,
    below_minimum: bool = False,
    include_inactive: bool = False,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    query = select(Product)
    if not include_inactive:
        query = query.where(Product.is_active.is_(True))
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(or_(Product.name.ilike(pattern), Product.sku.ilike(pattern)))
    if below_minimum:
        query = query.where(Product.quantity < Product.min_stock)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(query.order_by(Product.name).offset((page - 1) * page_size).limit(page_size)).all()
    return ProductPage(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED, summary="Create product")
def create_product(data: ProductCreate, db: Db, user: Admin):
    product = Product(**data.model_dump(), quantity=0)
    db.add(product)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SKU already exists") from None
    audit.record(db, user, "product.create", "product", product.id, sku=product.sku)
    db.commit()
    return product


@router.get("/{product_id}", response_model=ProductOut, summary="Get product")
def get_product(product_id: int, db: Db, _: CurrentUser):
    return get_product_or_404(db, product_id)


@router.patch("/{product_id}", response_model=ProductOut, summary="Update product")
def update_product(product_id: int, data: ProductUpdate, db: Db, user: Admin):
    product = get_product_or_404(db, product_id)
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        return product

    before = {field: getattr(product, field) for field in changes}
    for field, value in changes.items():
        setattr(product, field, value)
    audit.record(db, user, "product.update", "product", product.id, before=_plain(before), after=_plain(changes))
    db.commit()
    return product


@router.post("/{product_id}/movements", response_model=MovementOut, status_code=status.HTTP_201_CREATED, summary="Register stock movement")
def create_movement(product_id: int, data: MovementCreate, db: Db, user: Operator):
    try:
        movement = register_movement(db, product_id, user, data.type, data.quantity, data.note)
    except StockError as error:
        db.rollback()
        raise HTTPException(status_code=error.status_code, detail=error.message) from None
    db.commit()
    return _movement_out(movement)


@router.get("/{product_id}/movements", response_model=list[MovementOut], summary="Movement history")
def list_movements(product_id: int, db: Db, _: CurrentUser, limit: Annotated[int, Query(ge=1, le=100)] = 50):
    get_product_or_404(db, product_id)
    movements = db.scalars(
        select(Movement).where(Movement.product_id == product_id).order_by(Movement.created_at.desc(), Movement.id.desc()).limit(limit)
    ).all()
    return [_movement_out(m) for m in movements]


def _movement_out(movement: Movement) -> MovementOut:
    return MovementOut(
        id=movement.id,
        product_id=movement.product_id,
        type=movement.type,
        quantity=movement.quantity,
        balance_after=movement.balance_after,
        note=movement.note,
        user_name=movement.user.name,
        created_at=movement.created_at,
    )


def _plain(values: dict) -> dict:
    return {k: (v.value if hasattr(v, "value") else v) for k, v in values.items()}
