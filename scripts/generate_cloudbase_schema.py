#!/usr/bin/env python3
"""Generate the CloudBase shared-PG schema from the current SQLAlchemy head."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.database import Base  # noqa: E402
from backend.app import models  # noqa: E402,F401


OUTPUT = ROOT / "deployment/cloudbase_schema.sql"
RPC_TEMPLATE = ROOT / "scripts/cloudbase_rpc.sql"
HEAD_REVISION = "0009_partner_loop_personality"

# Existing CloudBase databases are already at an older schema. CREATE TABLE IF
# NOT EXISTS does not add new columns to those tables, so these compatibility
# alters must be emitted before every index/default/RPC that references them.
PRE_INDEX_COMPATIBILITY_ALTERS = """
ALTER TABLE users ADD COLUMN IF NOT EXISTS campus_verified BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS personality_consent BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS personality_traits JSON NOT NULL DEFAULT '{}'::json;
ALTER TABLE users ADD COLUMN IF NOT EXISTS personality_summary TEXT NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS personality_updated_at TIMESTAMP WITH TIME ZONE;
UPDATE users SET campus_verified = true
WHERE school_email IS NOT NULL OR school_uid IS NOT NULL OR is_mock = true;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS category VARCHAR(32) NOT NULL DEFAULT 'OTHER';
""".strip()

SERVER_DEFAULTS = """
ALTER TABLE users ALTER COLUMN identity_provider SET DEFAULT 'email';
ALTER TABLE users ALTER COLUMN school SET DEFAULT '中国科学技术大学';
ALTER TABLE users ALTER COLUMN bio SET DEFAULT '';
ALTER TABLE users ALTER COLUMN social_goals SET DEFAULT '[]'::json;
ALTER TABLE users ALTER COLUMN interests SET DEFAULT '[]'::json;
ALTER TABLE users ALTER COLUMN activities SET DEFAULT '[]'::json;
ALTER TABLE users ALTER COLUMN availability SET DEFAULT '[]'::json;
ALTER TABLE users ALTER COLUMN social_style SET DEFAULT '随和';
ALTER TABLE users ALTER COLUMN avoidances SET DEFAULT '[]'::json;
ALTER TABLE users ALTER COLUMN recommendation_enabled SET DEFAULT true;
ALTER TABLE users ALTER COLUMN verified SET DEFAULT false;
ALTER TABLE users ALTER COLUMN campus_verified SET DEFAULT false;
ALTER TABLE users ALTER COLUMN personality_consent SET DEFAULT false;
ALTER TABLE users ALTER COLUMN personality_traits SET DEFAULT '{}'::json;
ALTER TABLE users ALTER COLUMN personality_summary SET DEFAULT '';
ALTER TABLE users ALTER COLUMN token_version SET DEFAULT 0;
ALTER TABLE users ALTER COLUMN is_mock SET DEFAULT false;
ALTER TABLE users ALTER COLUMN created_at SET DEFAULT now();

ALTER TABLE activities ALTER COLUMN tags SET DEFAULT '[]'::json;
ALTER TABLE activities ALTER COLUMN capacity SET DEFAULT 20;
ALTER TABLE activities ALTER COLUMN public SET DEFAULT true;
ALTER TABLE preferences ALTER COLUMN weight SET DEFAULT 0;
ALTER TABLE preferences ALTER COLUMN updated_at SET DEFAULT now();
ALTER TABLE interactions ALTER COLUMN payload SET DEFAULT '{}'::json;
ALTER TABLE interactions ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE matches ALTER COLUMN status SET DEFAULT 'MATCHED';
ALTER TABLE matches ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE blocks ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE reports ALTER COLUMN status SET DEFAULT 'PENDING';
ALTER TABLE reports ALTER COLUMN category SET DEFAULT 'OTHER';
ALTER TABLE reports ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE messages ALTER COLUMN safety_result SET DEFAULT '{}'::json;
ALTER TABLE messages ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE agent_sessions ALTER COLUMN state SET DEFAULT '{}'::json;
ALTER TABLE agent_sessions ALTER COLUMN version SET DEFAULT 1;
ALTER TABLE agent_sessions ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE agent_sessions ALTER COLUMN updated_at SET DEFAULT now();
ALTER TABLE agent_traces ALTER COLUMN entries SET DEFAULT '[]'::json;
ALTER TABLE agent_traces ALTER COLUMN version SET DEFAULT 1;
ALTER TABLE agent_traces ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE agent_traces ALTER COLUMN updated_at SET DEFAULT now();
ALTER TABLE partner_requests ALTER COLUMN intent SET DEFAULT '{}'::json;
ALTER TABLE partner_requests ALTER COLUMN status SET DEFAULT 'OPEN';
ALTER TABLE partner_requests ALTER COLUMN note SET DEFAULT '';
ALTER TABLE partner_requests ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE partner_requests ALTER COLUMN updated_at SET DEFAULT now();
ALTER TABLE notifications ALTER COLUMN payload SET DEFAULT '{}'::json;
ALTER TABLE notifications ALTER COLUMN created_at SET DEFAULT now();
""".strip()


def generate() -> str:
    dialect = postgresql.dialect()
    sections = [
        "-- Generated from SQLAlchemy metadata and Alembic head 0001-0009.",
        "-- Run once in the CloudBase PostgreSQL SQL editor before deploying.",
        "BEGIN;",
    ]
    for table in Base.metadata.sorted_tables:
        sections.append(
            str(CreateTable(table, if_not_exists=True).compile(dialect=dialect)).strip()
            + ";"
        )
    # This order is part of the upgrade contract. In an existing 0008 schema,
    # the tables above already exist but the 0009 columns do not.
    sections.append(PRE_INDEX_COMPATIBILITY_ALTERS)
    for table in Base.metadata.sorted_tables:
        for index in sorted(table.indexes, key=lambda item: item.name or ""):
            sections.append(
                str(
                    CreateIndex(index, if_not_exists=True).compile(dialect=dialect)
                ).strip()
                + ";"
            )
    sections.extend(
        [
            SERVER_DEFAULTS,
            "CREATE TABLE IF NOT EXISTS alembic_version "
            "(version_num VARCHAR(128) PRIMARY KEY);",
            "DELETE FROM alembic_version;",
            f"INSERT INTO alembic_version(version_num) VALUES ('{HEAD_REVISION}');",
            RPC_TEMPLATE.read_text(encoding="utf-8").strip(),
            "COMMIT;",
            "",
        ]
    )
    return "\n\n".join(sections)


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(generate(), encoding="utf-8")
    print(f"CloudBase schema generated: {OUTPUT}")


if __name__ == "__main__":
    main()
