from fastapi.testclient import TestClient

from backend.app.database import get_db
from backend.app.main import app
from backend.app.services import SocialService


def test_only_active_matches_can_chat(db, sample_users, auth_headers):
    user, candidate, _ = sample_users

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            forbidden = client.post(
                f"/conversations/{candidate.id}/messages",
                json={"body": "你好"},
                headers=auth_headers(user.id),
            )
            assert forbidden.status_code == 403

            service = SocialService(db)
            service.record_feedback(user.id, candidate.id, "INTERESTED")
            service.record_feedback(candidate.id, user.id, "INTERESTED")

            sent = client.post(
                f"/conversations/{candidate.id}/messages",
                json={"body": "周六下午一起打球吗？"},
                headers=auth_headers(user.id),
            )
            assert sent.status_code == 201, sent.text
            assert sent.json()["sender_id"] == user.id

            conversations = client.get(
                "/conversations", headers=auth_headers(candidate.id)
            ).json()
            assert conversations[0]["partner"]["id"] == user.id
            assert conversations[0]["unread_count"] == 1

            received = client.get(
                f"/conversations/{user.id}/messages",
                headers=auth_headers(candidate.id),
            ).json()
            assert received[0]["body"] == "周六下午一起打球吗？"
            marked = client.post(
                f"/conversations/{user.id}/read",
                headers=auth_headers(candidate.id),
            ).json()
            assert marked["marked_read"] == 1

            risky = client.post(
                f"/conversations/{candidate.id}/messages",
                json={"body": "点这个贷款链接 https://bad.example"},
                headers=auth_headers(user.id),
            )
            assert risky.status_code == 422

            service.block_user(user.id, candidate.id)
            blocked = client.get(
                f"/conversations/{candidate.id}/messages",
                headers=auth_headers(user.id),
            )
            assert blocked.status_code == 403
    finally:
        app.dependency_overrides.clear()
