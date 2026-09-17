from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Movement, Product
from app.schemas import LowStockItem, Summary
from app.security import CurrentUser

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/low-stock", response_model=list[LowStockItem], summary="Products below minimum stock")
def low_stock(db: Annotated[Session, Depends(get_db)], _: CurrentUser):
    missing = (Product.min_stock - Product.quantity).label("missing")
    rows = db.execute(
        select(Product.id, Product.sku, Product.name, Product.unit, Product.quantity, Product.min_stock, missing)
        .where(Product.is_active.is_(True), Product.quantity < Product.min_stock)
        .order_by(missing.desc(), Product.name)
    ).all()
    return [LowStockItem.model_validate(row._mapping) for row in rows]


@router.get("/summary", response_model=Summary, summary="Stock overview")
def summary(db: Annotated[Session, Depends(get_db)], _: CurrentUser):
    active = Product.is_active.is_(True)
    week_ago = datetime.now(UTC) - timedelta(days=7)
    return Summary(
        active_products=db.scalar(select(func.count()).where(active)) or 0,
        below_minimum=db.scalar(select(func.count()).where(active, Product.quantity < Product.min_stock)) or 0,
        out_of_stock=db.scalar(select(func.count()).where(active, Product.quantity == 0)) or 0,
        movements_last_7_days=db.scalar(select(func.count()).select_from(Movement).where(Movement.created_at >= week_ago)) or 0,
    )
