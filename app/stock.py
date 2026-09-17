from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.models import Movement, MovementType, Product, User


class StockError(Exception):
    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def register_movement(db: Session, product_id: int, user: User, type_: MovementType, quantity: int, note: str | None) -> Movement:
    # trava a linha do produto: duas saidas ao mesmo tempo nao conseguem deixar o saldo negativo
    product = db.execute(select(Product).where(Product.id == product_id).with_for_update()).scalar_one_or_none()
    if product is None:
        raise StockError("Product not found", 404)
    if not product.is_active:
        raise StockError("Product is inactive")

    before = product.quantity
    if type_ == MovementType.entry:
        after = before + quantity
    elif type_ == MovementType.exit:
        if quantity > before:
            raise StockError(f"Insufficient stock: {before} available, {quantity} requested")
        after = before - quantity
    else:
        # ajuste de inventario: quantity e o valor contado
        after = quantity

    product.quantity = after
    movement = Movement(product_id=product.id, user_id=user.id, type=type_, quantity=quantity, balance_after=after, note=note)
    db.add(movement)
    db.flush()
    audit.record(db, user, f"movement.{type_.value}", "product", product.id, before=before, after=after, movement_id=movement.id)
    return movement
