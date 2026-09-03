"""Repair profile columns when the baseline adopted a partial users table.

Revision ID: 0007_repair_legacy_profile
Revises: 0006_agent_session_turn_lease
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_repair_legacy_profile"
down_revision = "0006_agent_session_turn_lease"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("users"):
        return
    columns = {column["name"] for column in inspector.get_columns("users")}
    additions = {
        "nickname": sa.Column(
            "nickname", sa.String(64), nullable=False, server_default="待完善"
        ),
        "school": sa.Column(
            "school",
            sa.String(128),
            nullable=False,
            server_default="中国科学技术大学",
        ),
        "campus": sa.Column(
            "campus", sa.String(64), nullable=False, server_default="待完善"
        ),
        "grade": sa.Column(
            "grade", sa.String(32), nullable=False, server_default="待完善"
        ),
        "major": sa.Column(
            "major", sa.String(128), nullable=False, server_default="待完善"
        ),
        "bio": sa.Column("bio", sa.Text(), nullable=False, server_default=""),
        "social_goals": sa.Column(
            "social_goals", sa.JSON(), nullable=False, server_default=sa.text("'[]'")
        ),
        "interests": sa.Column(
            "interests", sa.JSON(), nullable=False, server_default=sa.text("'[]'")
        ),
        "activities": sa.Column(
            "activities", sa.JSON(), nullable=False, server_default=sa.text("'[]'")
        ),
        "availability": sa.Column(
            "availability", sa.JSON(), nullable=False, server_default=sa.text("'[]'")
        ),
        "social_style": sa.Column(
            "social_style", sa.String(64), nullable=False, server_default="随和"
        ),
        "avoidances": sa.Column(
            "avoidances", sa.JSON(), nullable=False, server_default=sa.text("'[]'")
        ),
        "recommendation_enabled": sa.Column(
            "recommendation_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        "verified": sa.Column(
            "verified", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        "created_at": sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            # SQLite only accepts a constant default when ALTER TABLE adds a
            # column. New rows still receive the ORM's real current timestamp.
            server_default=sa.text("'1970-01-01 00:00:00'"),
        ),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column("users", column)


def downgrade() -> None:
    # This migration repairs an adopted legacy table. Dropping repaired user data is unsafe.
    pass
