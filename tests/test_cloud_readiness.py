"""Deployment artifacts remain local-SQLite and CloudBase-HTTP compatible."""

from pathlib import Path

from backend.app.config import Settings
from scripts.generate_cloudbase_schema import generate


ROOT = Path(__file__).resolve().parents[1]


def test_cloudbase_http_settings_require_only_env_and_api_key():
    settings = Settings(
        data_backend="cloudbase_http",
        cloudbase_env_id="campus-social-test",
        cloudbase_api_key="server-only-key",
    )
    settings.validate_runtime()
    assert settings.database_url.startswith("sqlite:")
    assert not hasattr(settings, "postgres_host")


def test_cloudbase_http_settings_reject_missing_server_key():
    settings = Settings(
        data_backend="cloudbase_http", cloudbase_env_id="campus-social-test"
    )
    try:
        settings.validate_runtime()
    except ValueError as exc:
        assert "CLOUDBASE_API_KEY" in str(exc)
    else:
        raise AssertionError("cloudbase_http must reject a missing API key")


def test_container_runs_seed_as_non_root_and_honors_port():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "USER app" in dockerfile
    assert "python scripts/seed_users.py" in dockerfile
    assert "${PORT:-8000}" in dockerfile
    assert "--host 0.0.0.0" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    package_script = (ROOT / "scripts/package_cloudbase.sh").read_text(encoding="utf-8")
    assert "deployment/cloudbase_schema.sql" in package_script


def test_cloud_dependencies_do_not_include_postgresql_wire_driver():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "psycopg" not in requirements.lower()
    assert "pymysql" not in requirements.lower()


def test_generated_cloudbase_schema_matches_current_generator():
    schema_path = ROOT / "deployment/cloudbase_schema.sql"
    schema = schema_path.read_text(encoding="utf-8")
    assert schema == generate()
    assert "0009_partner_loop_personality" in schema
    assert "CREATE TABLE IF NOT EXISTS users" in schema
    assert "CREATE TABLE IF NOT EXISTS agent_sessions" in schema
    assert "CREATE TABLE IF NOT EXISTS partner_requests" in schema
    assert "CREATE TABLE IF NOT EXISTS notifications" in schema
    assert "campus_record_feedback" in schema
    assert "campus_block_user" in schema
    assert "campus_agent_trace_save" in schema
    assert "SECURITY DEFINER" in schema
    assert "campus_require_service_role" in schema
    assert "postgresql+psycopg" not in schema


def test_compatibility_columns_are_created_before_dependent_statements():
    schema = generate()
    report_column = schema.index(
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS category"
    )
    report_index = schema.index(
        "CREATE INDEX IF NOT EXISTS ix_reports_category ON reports (category)"
    )
    report_default = schema.index(
        "ALTER TABLE reports ALTER COLUMN category SET DEFAULT 'OTHER'"
    )
    assert report_column < report_index < report_default

    for column in (
        "campus_verified",
        "personality_consent",
        "personality_traits",
        "personality_summary",
        "personality_updated_at",
    ):
        assert schema.index(
            f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {column}"
        ) < schema.index("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_school_email")
