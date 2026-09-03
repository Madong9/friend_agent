from backend.app.matching.scorer import score_candidate


def test_same_interest_and_time_get_higher_score(sample_users):
    user, close, distant = sample_users
    intent = {
        "goal": "find_activity_partner",
        "activity": "羽毛球",
        "availability": ["周六下午"],
    }
    assert (
        score_candidate(user, close, intent).total
        > score_candidate(user, distant, intent).total
    )


def test_matching_score_has_required_features(sample_users):
    score = score_candidate(sample_users[0], sample_users[1], {})
    assert set(score.features) == {
        "interest",
        "activity",
        "availability",
        "social_goal",
        "location",
        "feedback",
        "personality",
    }
    assert 0 <= score.total <= 1


def test_explicit_activity_and_compatible_goal_are_full_matches(sample_users):
    user, candidate, _ = sample_users
    score = score_candidate(
        user,
        candidate,
        {"goal": "find_activity_partner", "activity": "羽毛球"},
    )
    assert score.features["activity"] == 1.0
    assert score.features["social_goal"] == 1.0
