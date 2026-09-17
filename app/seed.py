"""Recria os dados de demonstracao.

    python -m app.seed

As senhas de operator e viewer sao publicas de proposito (estao na pagina /docs).
A senha do admin vem de ADMIN_PASSWORD e nunca fica no repositorio.
"""

import os
import sys

from sqlalchemy import delete

from app.db import SessionLocal
from app.models import AuditLog, Movement, MovementType, Product, Role, Unit, User
from app.security import hash_password
from app.stock import register_movement

PUBLIC_ACCOUNTS = [
    ("operador@demo.dev", "Operador Demo", Role.operator, "demo-operador-2026"),
    ("leitura@demo.dev", "Leitura Demo", Role.viewer, "demo-leitura-2026"),
]

PRODUCTS = [
    ("PAR-M6-40", "Parafuso sextavado M6 x 40 mm", Unit.un, 200, 850),
    ("ARR-M6", "Arruela lisa M6", Unit.un, 200, 120),
    ("LUV-NIT-M", "Luva nitrílica tamanho M (caixa)", Unit.cx, 10, 14),
    ("FITA-ISO-19", "Fita isolante 19 mm x 20 m", Unit.un, 30, 22),
    ("CABO-PP-2X15", "Cabo PP 2 x 1,5 mm", Unit.m, 100, 340),
    ("ABR-DISCO-115", "Disco de corte 115 mm", Unit.un, 25, 9),
    ("OLEO-15W40", "Óleo lubrificante 15W40", Unit.l, 20, 0),
    ("EPI-OCULOS", "Óculos de proteção incolor", Unit.un, 15, 31),
    ("CIMENTO-CP2", "Cimento CP II 50 kg", Unit.un, 8, 5),
    ("TINTA-BRANCA-18", "Tinta acrílica branca 18 L", Unit.un, 4, 6),
]


def reset(admin_password: str) -> None:
    with SessionLocal() as db:
        db.execute(delete(AuditLog))
        db.execute(delete(Movement))
        db.execute(delete(Product))
        db.execute(delete(User))
        db.flush()

        admin = User(email="admin@demo.dev", name="Admin", role=Role.admin, password_hash=hash_password(admin_password))
        db.add(admin)
        for email, name, role, password in PUBLIC_ACCOUNTS:
            db.add(User(email=email, name=name, role=role, password_hash=hash_password(password)))
        db.flush()

        operator = db.query(User).filter_by(email="operador@demo.dev").one()
        for sku, name, unit, min_stock, initial in PRODUCTS:
            product = Product(sku=sku, name=name, unit=unit, min_stock=min_stock, quantity=0)
            db.add(product)
            db.flush()
            if initial:
                register_movement(db, product.id, admin, MovementType.entry, initial, "Estoque inicial")

        # algumas saidas pra ter historico
        disco = db.query(Product).filter_by(sku="ABR-DISCO-115").one()
        register_movement(db, disco.id, operator, MovementType.exit, 3, "Manutenção da linha 2")
        luva = db.query(Product).filter_by(sku="LUV-NIT-M").one()
        register_movement(db, luva.id, operator, MovementType.exit, 2, None)
        db.commit()


if __name__ == "__main__":
    password = os.environ.get("ADMIN_PASSWORD", "")
    if len(password) < 16:
        sys.exit("Defina ADMIN_PASSWORD com pelo menos 16 caracteres")
    reset(password)
    print("dados de demonstracao recriados")
