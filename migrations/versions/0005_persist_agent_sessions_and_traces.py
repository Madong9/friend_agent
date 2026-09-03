"""Persist Agent sessions and traces with TTL metadata.

Revision ID: 0005_agent_state_persistence
Revises: 0004_add_ustc_identity_columns
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_agent_state_persistence"
down_revision = "0004_add_ustc_identity_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("agent_sessions"):
        op.create_table(
            "agent_sessions",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column(
                "user_id",
                sa.String(64),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("state", sa.JSON(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("active_turn_id", sa.String(64), nullable=True),
            sa.Column("lock_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_agent_sessions_user_id", "agent_sessions", ["user_id"])
        op.create_index(
            "ix_agent_sessions_expires_at", "agent_sessions", ["expires_at"]
        )

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("agent_traces"):
        op.create_table(
            "agent_traces",
            sa.Column("session_id", sa.String(64), primary_key=True),
            sa.Column(
                "user_id",
                sa.String(64),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("entries", sa.JSON(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_agent_traces_user_id", "agent_traces", ["user_id"])
        op.create_index("ix_agent_traces_expires_at", "agent_traces", ["expires_at"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("agent_traces"):
        op.drop_table("agent_traces")
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("agent_sessions"):
        op.drop_table("agent_sessions")
