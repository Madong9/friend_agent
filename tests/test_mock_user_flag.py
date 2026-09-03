"""Mock user flags: is_mock exposure, SHOW_MOCK_USERS filter, nullable openid."""

from backend.app.config import get_settings
from backend.app.matching import MatchingEngine
from backend.app.models import User
from backend.app.tools.privacy import public_user


def test_mock_user_flag_is_exposed_in_public_schema(db, sample_users):
    user, mock_candidate, _ = sample_users
    mock_candidate.is_mock = True
    db.commit()
    public = public_user(mock_candidate)
    assert public["is_mock"] is True
    assert public_user(user)["is_mock"] is False
    assert "wechat_openid" not in public
    assert "password_hash" not in public
    assert "school_email" not in public


def test_show_mock_users_hides_mock_candidates(db, sample_users, monkeypatch):
    monkeypatch.setenv("SHOW_MOCK_USERS", "false")
    get_settings.cache_clear()
    try:
        sample_users[2].is_mock = True
        db.commit()
        engine = MatchingEngine(db)
        candidates = engine.retrieve_candidates("a")
        assert all(candidate.is_mock is False for candidate in candidates)
        assert [candidate.id for candidate in candidates] == ["b"]
    finally:
        get_settings.cache_clear()


def test_mock_users_are_included_by_default(db, sample_users):
    sample_users[2].is_mock = True
    db.commit()
    engine = MatchingEngine(db)
    candidates = engine.retrieve_candidates("a")
    assert [candidate.id for candidate in candidates] == ["b", "c"]


def test_wechat_openid_allows_empty_for_seed_users(db):
    user = User(
        id="seed-only",
        nickname="种子用户",
        school="中国科学技术大学",
        campus="西区",
        grade="研一",
        major="计算机",
        is_mock=True,
    )
    db.add(user)
    db.commit()
    assert user.wechat_openid is None
