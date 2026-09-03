from backend.app.matching.engine import MatchingEngine
from backend.app.services import SocialService


def test_blocked_users_never_match(db, sample_users):
    user, candidate, _ = sample_users
    SocialService(db).block_user(user.id, candidate.id)
    result = MatchingEngine(db).recommend(user.id, {}, limit=10)
    assert candidate.id not in [item["candidate"].id for item in result]
    reverse = MatchingEngine(db).recommend(candidate.id, {}, limit=10)
    assert user.id not in [item["candidate"].id for item in reverse]
