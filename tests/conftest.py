import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.config import get_settings
from backend.app.database import Base
from backend.app.models import User
from backend.app.security import create_access_token, hash_password


TEST_PASSWORD = "TestPass123!"
TEST_PASSWORD_HASH = hash_password(TEST_PASSWORD)


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    """Tests must never depend on the developer's real .env (LLM keys, dev auth)."""
    monkeypatch.setenv("DATA_BACKEND", "sqlite")
    monkeypatch.setenv("DEV_AUTH_MODE", "false")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    try:
        Base.metadata.create_all(engine)
        with Session(engine, expire_on_commit=False) as session:
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def sample_users(db):
    users = [
        User(
            id="a",
            nickname="甲",
            school_email="a@ustc.edu.cn",
            school="中国科学技术大学",
            campus="西区",
            grade="研一",
            major="计算机",
            interests=["羽毛球", "摄影"],
            activities=["羽毛球"],
            availability=["周六下午"],
            social_goals=["运动搭子"],
            password_hash=TEST_PASSWORD_HASH,
            verified=True,
            campus_verified=True,
        ),
        User(
            id="b",
            nickname="乙",
            school_email="b@ustc.edu.cn",
            school="中国科学技术大学",
            campus="西区",
            grade="研一",
            major="新闻",
            interests=["羽毛球", "摄影"],
            activities=["羽毛球"],
            availability=["周六下午"],
            social_goals=["运动搭子"],
            password_hash=TEST_PASSWORD_HASH,
            verified=True,
            campus_verified=True,
        ),
        User(
            id="c",
            nickname="丙",
            school_email="c@ustc.edu.cn",
            school="中国科学技术大学",
            campus="东区",
            grade="大二",
            major="金融",
            interests=["阅读"],
            activities=["读书会"],
            availability=["工作日上午"],
            social_goals=["兴趣朋友"],
            password_hash=TEST_PASSWORD_HASH,
            verified=True,
            campus_verified=True,
        ),
    ]
    db.add_all(users)
    db.commit()
    return users


@pytest.fixture
def auth_headers():
    def make_headers(user_id: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(user_id)}"}

    return make_headers
