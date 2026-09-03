"""Add database lease fields to already-created Agent session tables.

Revision ID: 0006_agent_session_turn_lease
Revises: 0005_agent_state_persistence
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_agent_session_turn_lease"
down_revision = "0005_agent_state_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("agent_sessions"):
        return
    columns = {column["name"] for column in inspector.get_columns("agent_sessions")}
    if "active_turn_id" not in columns:
        op.add_column(
            "agent_sessions", sa.Column("active_turn_id", sa.String(64), nullable=True)
        )
    if "lock_expires_at" not in columns:
        op.add_column(
            "agent_sessions",
            sa.Column("lock_expires_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("agent_sessions"):
        return
    columns = {column["name"] for column in inspector.get_columns("agent_sessions")}
    if "lock_expires_at" in columns:
        with op.batch_alter_table("agent_sessions") as batch_op:
            batch_op.drop_column("lock_expires_at")
    if "active_turn_id" in columns:
        with op.batch_alter_table("agent_sessions") as batch_op:
            batch_op.drop_column("active_turn_id")
