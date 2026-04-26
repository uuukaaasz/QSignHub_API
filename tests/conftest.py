import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.database import Base, get_db
from app.models import Organization, User, ApiKey
from app.auth import hash_password, generate_api_key

TEST_DB_URL = "sqlite+aiosqlite:///./test.db"


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine):
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db):
    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def org(db: AsyncSession) -> Organization:
    o = Organization(name="Test Org", slug="test-org", email="org@test.com")
    db.add(o)
    await db.flush()
    return o


@pytest_asyncio.fixture
async def owner(db: AsyncSession, org: Organization) -> User:
    u = User(
        organization_id=org.id,
        email="owner@test.com",
        full_name="Test Owner",
        hashed_password=hash_password("Str0ngP@ss!"),
        role="owner",
        is_active=True,
        is_verified=True,
    )
    db.add(u)
    await db.flush()
    return u


@pytest_asyncio.fixture
async def api_key_raw(db: AsyncSession, org: Organization) -> str:
    raw, key_hash = generate_api_key("live")
    key = ApiKey(
        organization_id=org.id,
        name="Test Key",
        key_hash=key_hash,
        key_prefix=raw[:20],
        environment="live",
        is_active=True,
    )
    db.add(key)
    await db.flush()
    return raw


@pytest_asyncio.fixture
async def auth_headers(client, owner):
    resp = await client.post("/api/v1/auth/token", json={"email": owner.email, "password": "Str0ngP@ss!"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def api_headers(api_key_raw):
    return {"X-API-Key": api_key_raw}
