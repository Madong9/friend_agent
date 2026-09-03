from fastapi.testclient import TestClient

from backend.app.database import get_db
from backend.app.main import app
from backend.app.security import create_access_token


def test_business_jwt_accepts_standard_and_campus_headers_with_strict_precedence(
    db, sample_users
):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    token_a = create_access_token("a")
    token_b = create_access_token("b")
    try:
        with TestClient(app) as client:
            standard = client.get(
                "/auth/me", headers={"Authorization": f"Bearer {token_a}"}
            )
            assert standard.status_code == 200
            assert standard.json()["id"] == "a"

            sdk_header = client.get(
                "/auth/me",
                headers={
                    "Authorization": "Bearer cloudbase-publishable-key",
                    "X-Campus-Authorization": f"Bearer {token_a}",
                },
            )
            assert sdk_header.status_code == 200
            assert sdk_header.json()["id"] == "a"

            forged = client.get(
                "/auth/me",
                headers={
                    "Authorization": f"Bearer {token_a}",
                    "X-Campus-Authorization": "Bearer forged-token",
                },
            )
            assert forged.status_code == 401

            campus_takes_precedence = client.get(
                "/auth/me",
                headers={
                    "Authorization": f"Bearer {token_b}",
                    "X-Campus-Authorization": f"Bearer {token_a}",
                },
            )
            assert campus_takes_precedence.status_code == 200
            assert campus_takes_precedence.json()["id"] == "a"

            for public_path in ("/health", "/__tcb_probe__"):
                response = client.get(
                    public_path,
                    headers={"X-Campus-Authorization": "not-a-bearer-token"},
                )
                assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
