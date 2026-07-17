"""
إعدادات الاختبار المشتركة — قاعدة بيانات مؤقتة + عميل اختبار
"""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

# ── ضبط المتغيرات أولاً قبل أي استيراد ──────────────
os.environ["SECRET_KEY"] = "test-secret-key-do-not-use-in-production"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ENVIRONMENT"] = "test"
os.environ["COOKIE_SECURE"] = "false"

from app.database import Base
import app.database as _db_module

# ── محرك in-memory مشترك ───────────────────────────
_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(bind=_test_engine)

# نعوّض SessionLocal في وحدة database بالكامل
# حتى الدوال التي تستخدم SessionLocal مباشرة (مثل _issue_tokens)
_db_module.engine = _test_engine
_db_module.SessionLocal = _TestSession

# نستورد app بعد التعديل
from app.main import app
from app.database import get_db


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """إنشاء وحذف الجداول قبل/بعد كل اختبار"""
    Base.metadata.create_all(bind=_test_engine)
    yield
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """إعادة تعيين Rate Limiter بين كل اختبار"""
    from app.limiter import limiter
    limiter.reset()
    yield


@pytest.fixture()
def db_session():
    session = _TestSession()
    yield session
    session.close()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app, base_url="http://testserver", raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture()
def auth_client(client):
    """عميل اختبار مسجّل دخول تلقائياً"""
    res = client.post("/api/auth/register", json={
        "name": "مختبر",
        "email": "test@sawa.dev",
        "password": "Test1234!",
    })
    assert res.status_code == 201
    return client
