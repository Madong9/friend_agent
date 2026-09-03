from backend.app.matching.filters import hard_filter_reason
from backend.app.models import Interaction


def test_self_and_time_conflict_are_filtered(db, sample_users):
    user, _, distant = sample_users
    assert hard_filter_reason(db, user, user, {}) == "self"
    intent = {"availability": ["周六下午"]}
    assert hard_filter_reason(db, user, distant, intent) == "time_conflict"


def test_visibility_verification_and_explicit_constraints(db, sample_users):
    user, candidate, distant = sample_users

    candidate.recommendation_enabled = False
    assert hard_filter_reason(db, user, candidate, {}) == "recommendation_disabled"
    candidate.recommendation_enabled = True
    candidate.verified = False
    assert hard_filter_reason(db, user, candidate, {}) == "not_verified"
    candidate.verified = True
    candidate.school_email = None
    assert hard_filter_reason(db, user, candidate, {}) == "not_school_identity"
    candidate.wechat_openid = "wx-openid-b"
    assert hard_filter_reason(db, user, candidate, {}) is None
    candidate.wechat_openid = None
    candidate.school_email = "b@example.edu"

    assert (
        hard_filter_reason(
            db,
            user,
            distant,
            {"campus": "西区", "hard_constraints": ["campus"]},
        )
        == "campus_constraint"
    )

    db.add(
        Interaction(
            actor_id=user.id,
            target_id=candidate.id,
            kind="NOT_RELEVANT",
            payload={},
        )
    )
    db.commit()
    assert hard_filter_reason(db, user, candidate, {}) == "previous_strong_rejection"
