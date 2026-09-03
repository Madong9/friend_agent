from backend.app.services import SocialService


def test_mutual_interest_creates_match_only_after_both_sides(db, sample_users):
    user, candidate, _ = sample_users
    service = SocialService(db)
    assert service.record_feedback(user.id, candidate.id, "INTERESTED") is None
    match = service.record_feedback(candidate.id, user.id, "LIKE")
    assert match is not None
    assert match.status == "MATCHED"
    assert len(service.list_matches(user.id)) == 1


def test_feedback_adjustment_is_bounded(db, sample_users):
    user, candidate, _ = sample_users
    service = SocialService(db)
    for _ in range(20):
        service.record_feedback(user.id, candidate.id, "LIKE")
    adjustment = service.memory.feedback_adjustments(user.id)[candidate.id]
    assert 0.25 <= adjustment <= 0.75


def test_feedback_updates_bounded_preference_memory(db, sample_users):
    user, candidate, similar = sample_users
    similar.interests = list(candidate.interests)
    similar.activities = list(candidate.activities)
    db.commit()
    service = SocialService(db)

    service.record_feedback(user.id, candidate.id, "LIKE")

    learned = service.memory.preference_adjustment(user.id, similar)
    assert 0.5 < learned <= 0.75
    combined = service.memory.ranking_feedback_adjustments(user.id, [similar])
    assert 0.5 < combined[similar.id] <= 0.75


def test_latest_pass_cancels_old_interest(db, sample_users):
    user, candidate, _ = sample_users
    service = SocialService(db)
    service.record_feedback(candidate.id, user.id, "INTERESTED")
    service.record_feedback(candidate.id, user.id, "PASS")
    assert service.record_feedback(user.id, candidate.id, "INTERESTED") is None


def test_block_revokes_existing_match_and_future_feedback(db, sample_users):
    import pytest

    user, candidate, _ = sample_users
    service = SocialService(db)
    service.record_feedback(user.id, candidate.id, "INTERESTED")
    assert service.record_feedback(candidate.id, user.id, "INTERESTED") is not None

    service.block_user(user.id, candidate.id)
    assert service.list_matches(user.id) == []
    with pytest.raises(ValueError, match="blocked relation"):
        service.record_feedback(candidate.id, user.id, "LIKE")
