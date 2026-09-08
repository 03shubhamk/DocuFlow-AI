"""
DocuFlow AI — Pytest Configuration and Test Fixtures.

Provides:
- In-memory SQLite async database engine and clean session per test
- FastAPI dependency overrides for TestClient
- Factory fixtures for users, tokens, and documents
"""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db, get_storage_dep
from app.config import Settings, get_settings
from app.domain.entities import UserRole
from app.infrastructure.database.models import Base, TenantModel, UserModel
from app.infrastructure.security.tokens import create_access_token, hash_password
from app.infrastructure.storage.memory_storage import InMemoryStorage
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

_shared_in_memory_storage = InMemoryStorage()


@pytest.fixture(scope="session", autouse=True)
def set_testing_env() -> None:
    import os
    os.environ["ENVIRONMENT"] = "testing"
    get_settings.cache_clear()
    from app.infrastructure.processors import get_document_processor
    from app.infrastructure.storage import get_storage
    from app.infrastructure.tasks.celery_app import celery_app

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    get_storage.cache_clear()
    get_document_processor.cache_clear()



@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return get_settings()



@pytest.fixture
async def test_engine():
    """Create a fresh in-memory SQLite database for each test."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session and roll back changes after test."""
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def in_memory_storage() -> InMemoryStorage:
    _shared_in_memory_storage.clear()
    return _shared_in_memory_storage




@pytest.fixture
async def client(test_engine, in_memory_storage: InMemoryStorage) -> AsyncGenerator[TestClient, None]:
    """FastAPI TestClient with database and storage dependencies overridden."""
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    def override_get_storage() -> InMemoryStorage:
        return in_memory_storage

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage_dep] = override_get_storage
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()



@pytest.fixture
async def test_tenant(db_session: AsyncSession) -> TenantModel:
    tenant = TenantModel(
        id=uuid.uuid4(),
        name="Acme Corp",
        slug=f"acme-{uuid.uuid4().hex[:6]}",
        is_active=True,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest.fixture
async def test_user(db_session: AsyncSession, test_tenant: TenantModel) -> UserModel:
    user = UserModel(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        email="user@acme.com",
        hashed_password=hash_password("Password123!"),
        full_name="Standard User",
        role=UserRole.USER.value,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_admin(db_session: AsyncSession, test_tenant: TenantModel) -> UserModel:
    admin = UserModel(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        email="admin@acme.com",
        hashed_password=hash_password("AdminPassword123!"),
        full_name="Admin User",
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest.fixture
def user_auth_headers(test_settings: Settings, test_user: UserModel) -> dict[str, str]:
    token, _ = create_access_token(
        settings=test_settings,
        subject=str(test_user.id),
        tenant_id=str(test_user.tenant_id),
        role=test_user.role,
        email=test_user.email,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(test_settings: Settings, test_admin: UserModel) -> dict[str, str]:
    token, _ = create_access_token(
        settings=test_settings,
        subject=str(test_admin.id),
        tenant_id=str(test_admin.tenant_id),
        role=test_admin.role,
        email=test_admin.email,
    )
    return {"Authorization": f"Bearer {token}"}
