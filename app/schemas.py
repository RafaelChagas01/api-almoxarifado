from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field, StringConstraints, model_validator

from app.models import MovementType, Role, Unit

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
Sku = Annotated[
    str,
    BeforeValidator(lambda v: v.strip().upper() if isinstance(v, str) else v),
    StringConstraints(pattern=r"^[A-Z0-9][A-Z0-9-]{2,29}$"),
]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]


class Input(BaseModel):
    # campo desconhecido gera 422, entao ninguem manda "quantity" ou "role" escondido
    model_config = ConfigDict(extra="forbid")


class Output(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int


class UserOut(Output):
    id: int
    email: str
    name: str
    role: Role
    is_active: bool


class UserCreate(Input):
    email: EmailStr
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
    password: Annotated[str, StringConstraints(min_length=10, max_length=128)]
    role: Role = Role.viewer


class UserUpdate(Input):
    role: Role | None = None
    is_active: bool | None = None


class ProductCreate(Input):
    sku: Sku
    name: Name
    unit: Unit
    min_stock: int = Field(default=0, ge=0, le=1_000_000)


class ProductUpdate(Input):
    name: Name | None = None
    unit: Unit | None = None
    min_stock: int | None = Field(default=None, ge=0, le=1_000_000)
    is_active: bool | None = None


class ProductOut(Output):
    id: int
    sku: str
    name: str
    unit: Unit
    quantity: int
    min_stock: int
    is_active: bool
    updated_at: datetime


class ProductPage(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    page_size: int


class MovementCreate(Input):
    type: MovementType
    quantity: int = Field(ge=0, le=1_000_000)
    note: Note | None = None

    @model_validator(mode="after")
    def check_rules(self):
        if self.type != MovementType.adjustment and self.quantity == 0:
            raise ValueError("quantity must be greater than zero for entries and exits")
        if self.type == MovementType.adjustment and not self.note:
            raise ValueError("adjustments need a note explaining the count")
        return self


class MovementOut(Output):
    id: int
    product_id: int
    type: MovementType
    quantity: int
    balance_after: int
    note: str | None
    user_name: str
    created_at: datetime


class LowStockItem(Output):
    id: int
    sku: str
    name: str
    unit: Unit
    quantity: int
    min_stock: int
    missing: int


class Summary(BaseModel):
    active_products: int
    below_minimum: int
    out_of_stock: int
    movements_last_7_days: int


class AuditOut(Output):
    id: int
    user_id: int | None
    action: str
    entity: str
    entity_id: int | None
    details: dict
    created_at: datetime
