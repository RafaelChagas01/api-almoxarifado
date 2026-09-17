import os

os.environ.setdefault("JWT_SECRET", "segredo-so-para-testes-com-mais-de-32-caracteres")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import db as db_module
from app.db import Base, get_db
from app.main import app
from app.models import Product, Role, Unit, User
from app.routers import auth
from app.security import hash_password

PASSWORD = "senha-de-teste-123"


@pytest.fixture
def session_factory():
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        engine = db_module.build_engine(url)
    else:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(session_factory, monkeypatch):
    def override():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override
    monkeypatch.setattr(db_module, "SessionLocal", session_factory)
    auth.limiter.failures.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def users(session_factory):
    with session_factory() as db:
        created = {}
        for role in Role:
            user = User(email=f"{role.value}@teste.dev", name=role.value.title(), role=role, password_hash=hash_password(PASSWORD))
            db.add(user)
            created[role] = user
        db.commit()
        return created


@pytest.fixture
def product(session_factory):
    with session_factory() as db:
        item = Product(sku="PAR-M6-40", name="Parafuso M6", unit=Unit.un, quantity=10, min_stock=20)
        db.add(item)
        db.commit()
        return item


def token_for(client: TestClient, role: Role) -> dict:
    response = client.post("/auth/token", data={"username": f"{role.value}@teste.dev", "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def auth_headers(client, users):
    return {role: token_for(client, role) for role in Role}
