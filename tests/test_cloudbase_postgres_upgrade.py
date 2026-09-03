"""Real PostgreSQL regression for the deployed CloudBase 0008 -> 0009 path."""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import pytest

from scripts.generate_cloudbase_schema import generate


ROOT = Path(__file__).resolve().parents[1]
LEGACY_SCHEMA = ROOT / "tests" / "fixtures" / "cloudbase_0008_schema.sql"
POSTGRES_IMAGE = "postgres:16-alpine"


def _run(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(args),
        input=input_text,
        capture_output=True,
        text=True,
        check=True,
    )


def _psql(container: str, sql: str, *, query: bool = False) -> str:
    command = [
        "docker",
        "exec",
        "-i",
        container,
        "psql",
        "-X",
        "--set=ON_ERROR_STOP=1",
        "--username=postgres",
        "--dbname=campus_upgrade",
    ]
    if query:
        command.extend(["--tuples-only", "--no-align", "--field-separator=|"])
    return _run(*command, input_text=sql).stdout.strip()


def _require_local_postgres_image() -> None:
    if shutil.which("docker") is None:
        pytest.skip("Docker is required for the real PostgreSQL upgrade regression")
    daemon = subprocess.run(
        ["docker", "info"], capture_output=True, text=True, check=False
    )
    if daemon.returncode:
        pytest.skip("Docker daemon is unavailable")
    image = subprocess.run(
        ["docker", "image", "inspect", POSTGRES_IMAGE],
        capture_output=True,
        text=True,
        check=False,
    )
    if image.returncode:
        pytest.skip(f"local image {POSTGRES_IMAGE} is required; tests never pull images")


def test_real_postgresql_cloudbase_schema_upgrades_0008_without_data_loss():
    _require_local_postgres_image()
    container = f"campus-social-pg-upgrade-{uuid4().hex[:10]}"
    _run(
        "docker",
        "run",
        "--detach",
        "--rm",
        "--name",
        container,
        "--env",
        "POSTGRES_PASSWORD=upgrade-test-only",
        "--env",
        "POSTGRES_DB=campus_upgrade",
        POSTGRES_IMAGE,
    )
    try:
        for _ in range(80):
            logs = subprocess.run(
                ["docker", "logs", container],
                capture_output=True,
                text=True,
                check=False,
            )
            ready = subprocess.run(
                [
                    "docker",
                    "exec",
                    container,
                    "pg_isready",
                    "--username=postgres",
                    "--dbname=campus_upgrade",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            # The official image briefly exposes an initialization server and
            # then restarts PostgreSQL. pg_isready alone can catch that first
            # transient server, so also require the entrypoint completion mark.
            if (
                "PostgreSQL init process complete; ready for start up."
                in logs.stdout + logs.stderr
                and ready.returncode == 0
            ):
                break
            time.sleep(0.25)
        else:
            pytest.fail("temporary PostgreSQL did not become ready")

        _psql(container, LEGACY_SCHEMA.read_text(encoding="utf-8"))
        before = _psql(
            container,
            """
            SELECT
                (SELECT count(*) FROM users),
                (SELECT count(*) FROM reports),
                (SELECT count(*) FROM interactions),
                (SELECT count(*) FROM preferences),
                (SELECT version_num FROM alembic_version);
            """,
            query=True,
        )
        assert before == "2|1|1|1|0008_add_wechat_and_mock_flags"

        # This is the exact generated artifact copied into CloudBase's editor.
        _psql(container, generate())

        columns = _psql(
            container,
            """
            SELECT table_name || '.' || column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND (
                (table_name = 'users' AND column_name IN (
                    'campus_verified', 'personality_consent',
                    'personality_traits', 'personality_summary',
                    'personality_updated_at'
                ))
                OR (table_name = 'reports' AND column_name = 'category')
              )
            ORDER BY table_name, column_name;
            """,
            query=True,
        ).splitlines()
        assert columns == [
            "reports.category",
            "users.campus_verified",
            "users.personality_consent",
            "users.personality_summary",
            "users.personality_traits",
            "users.personality_updated_at",
        ]
        assert _psql(
            container,
            "SELECT to_regclass('public.ix_reports_category');",
            query=True,
        ) == "ix_reports_category"
        assert _psql(
            container,
            """
            SELECT to_regclass('public.partner_requests'),
                   to_regclass('public.notifications'),
                   version_num
            FROM alembic_version;
            """,
            query=True,
        ) == "partner_requests|notifications|0009_partner_loop_personality"

        # Old rows and business values survive. Backfill only marks identities
        # that already had a school email/UID (or were explicit mock users).
        users = _psql(
            container,
            """
            SELECT id, nickname, bio, token_version, campus_verified,
                   personality_consent, personality_traits::text,
                   personality_summary
            FROM users ORDER BY id;
            """,
            query=True,
        ).splitlines()
        assert users == [
            "legacy-verified|历史认证用户|需要被完整保留的历史简介|2|t|f|{}|",
            "legacy-wechat|历史微信用户|微信用户历史简介|0|f|f|{}|",
        ]
        report = _psql(
            container,
            """
            SELECT reporter_id, reported_id, reason, status, category
            FROM reports;
            """,
            query=True,
        )
        assert report == (
            "legacy-verified|legacy-wechat|历史举报原因必须保留|PENDING|OTHER"
        )
        after = _psql(
            container,
            """
            SELECT
                (SELECT count(*) FROM users),
                (SELECT count(*) FROM reports),
                (SELECT count(*) FROM interactions),
                (SELECT count(*) FROM preferences),
                (SELECT count(*) FROM activities),
                (SELECT count(*) FROM partner_requests),
                (SELECT count(*) FROM notifications);
            """,
            query=True,
        )
        assert after == "2|1|1|1|1|0|0"

        # Re-running after a successful console execution remains non-destructive.
        _psql(container, generate())
        assert _psql(
            container,
            "SELECT count(*), min(reason), min(category) FROM reports;",
            query=True,
        ) == "1|历史举报原因必须保留|OTHER"
    finally:
        subprocess.run(
            ["docker", "rm", "--force", container],
            capture_output=True,
            text=True,
            check=False,
        )
