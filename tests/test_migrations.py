import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


ROOT = Path(__file__).resolve().parents[1]


def migration_head() -> str:
    config = Config(ROOT / "alembic.ini")
    head = ScriptDirectory.from_config(config).get_current_head()
    assert head is not None
    return head


def run_upgrade(database_path: Path) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{database_path}"
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def schema(database_path: Path) -> tuple[set[str], set[str], str]:
    with closing(sqlite3.connect(database_path)) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
        revision = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()[0]
    return tables, columns, revision


def table_columns(database_path: Path, table: str) -> set[str]:
    with closing(sqlite3.connect(database_path)) as connection:
        return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def test_migrations_create_fresh_database(tmp_path):
    database_path = tmp_path / "fresh.db"
    run_upgrade(database_path)
    tables, columns, revision = schema(database_path)
    assert {
        "users",
        "messages",
        "matches",
        "agent_sessions",
        "agent_traces",
        "partner_requests",
        "notifications",
        "alembic_version",
    } <= tables
    assert {
        "password_hash",
        "verified",
        "school_email",
        "identity_provider",
        "token_version",
        "last_token_revoked_at",
        "school_uid",
        "school_display_name",
        "campus_verified",
        "personality_consent",
        "personality_traits",
        "personality_summary",
        "personality_updated_at",
    } <= columns
    assert revision == migration_head()
    assert {
        "id",
        "user_id",
        "state",
        "version",
        "active_turn_id",
        "lock_expires_at",
        "expires_at",
    } <= table_columns(database_path, "agent_sessions")
    assert {
        "session_id",
        "user_id",
        "entries",
        "version",
        "expires_at",
    } <= table_columns(database_path, "agent_traces")

    run_upgrade(database_path)
    assert schema(database_path)[2] == revision


def test_migrations_adopt_existing_database_without_data_loss(tmp_path):
    database_path = tmp_path / "legacy.db"
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("CREATE TABLE users (id VARCHAR(64) PRIMARY KEY)")
        connection.execute("INSERT INTO users (id) VALUES ('legacy-user')")
        connection.commit()

    run_upgrade(database_path)
    _, columns, revision = schema(database_path)
    with closing(sqlite3.connect(database_path)) as connection:
        assert connection.execute("SELECT id FROM users").fetchone()[0] == "legacy-user"
    assert {
        "password_hash",
        "nickname",
        "school",
        "campus",
        "grade",
        "major",
        "bio",
        "social_goals",
        "interests",
        "activities",
        "availability",
        "social_style",
        "avoidances",
        "recommendation_enabled",
        "verified",
        "created_at",
        "school_email",
        "identity_provider",
        "token_version",
        "last_token_revoked_at",
        "school_uid",
        "school_display_name",
        "campus_verified",
        "personality_consent",
        "personality_traits",
        "personality_summary",
        "personality_updated_at",
    } <= columns
    assert revision == migration_head()
    assert "state" in table_columns(database_path, "agent_sessions")
    assert "entries" in table_columns(database_path, "agent_traces")
