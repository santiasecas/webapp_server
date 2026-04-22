"""
tests/test_platform.py — Integration tests using in-memory SQLite.

Run with:
    pip install pytest pytest-asyncio httpx aiosqlite
    pytest tests/ -v
"""
import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Use SQLite in-memory for tests (no Postgres needed)
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

# Patch settings before importing the app
os.environ.update({
    "ENVIRONMENT": "test",
    "DEBUG": "true",
    "DATABASE_URL": TEST_DB_URL,
    "DB_HOST": "localhost",
    "DB_NAME": "test",
    "DB_USER": "test",
    "DB_PASSWORD": "test",
    "HTPASSWD_FILE": "tests/.htpasswd_test",
    "SECRET_KEY": "test-secret-key",
})


@pytest.fixture(scope="session", autouse=True)
def create_test_htpasswd(tmp_path_factory):
    """Create a temporary .htpasswd for tests."""
    import bcrypt
    path = "tests/.htpasswd_test"
    os.makedirs("tests", exist_ok=True)
    hashed = bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode().replace("$2b$", "$2y$")
    with open(path, "w") as f:
        f.write(f"testuser:{hashed}\n")
    yield
    if os.path.exists(path):
        os.remove(path)


@pytest_asyncio.fixture
async def client():
    """Async test client with overridden DB."""
    from core.database import Base, get_db

    engine = create_async_engine(TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    from main import app
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    await engine.dispose()


# ── Tests ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("ok", "degraded")
    assert "version" in data


@pytest.mark.asyncio
async def test_dashboard_redirect(client):
    r = await client.get("/", follow_redirects=False)
    assert r.status_code == 307


@pytest.mark.asyncio
async def test_contacts_requires_auth(client):
    r = await client.get("/apps/contacts/")
    assert r.status_code == 401
    assert "WWW-Authenticate" in r.headers


@pytest.mark.asyncio
async def test_contacts_with_auth(client):
    r = await client.get("/apps/contacts/", auth=("testuser", "testpass"))
    assert r.status_code == 200
    assert "Contact" in r.text


@pytest.mark.asyncio
async def test_create_contact(client):
    r = await client.post(
        "/apps/contacts/new",
        data={
            "name": "Alice Example",
            "email": "alice@example.com",
            "phone": "+34 600 000 001",
            "department": "Engineering",
            "notes": "",
        },
        auth=("testuser", "testpass"),
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "/apps/contacts/" in r.headers["location"]


@pytest.mark.asyncio
async def test_duplicate_email(client):
    auth = ("testuser", "testpass")
    data = {"name": "Bob", "email": "bob@example.com", "phone": "", "department": "", "notes": ""}
    await client.post("/apps/contacts/new", data=data, auth=auth)
    r = await client.post("/apps/contacts/new", data=data, auth=auth)
    assert r.status_code == 422
    assert "already" in r.text.lower()


@pytest.mark.asyncio
async def test_invalid_auth(client):
    r = await client.get("/apps/contacts/", auth=("testuser", "wrongpassword"))
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_contact_not_found(client):
    r = await client.get("/apps/contacts/99999", auth=("testuser", "testpass"))
    assert r.status_code == 404
