"""Add password authentication and matched-user messages.

Revision ID: 0002_add_auth_and_messages
Revises: 0001_existing_schema_baseline
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_add_auth_and_messages"
down_revision = "0001_existing_schema_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alembic creates ``alembic_version.version_num`` as VARCHAR(32). SQLite
    # doesn't enforce that length, but PostgreSQL does and later descriptive
    # revision IDs (starting with 0003) are longer than 32 characters. Widen it
    # before Alembic records this revision so fresh PG environments can advance.
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "alembic_version",
            "version_num",
            existing_type=sa.String(length=32),
            type_=sa.String(length=128),
            existing_nullable=False,
        )

    inspector = sa.inspect(op.get_bind())
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "password_hash" not in user_columns:
        op.add_column(
            "users", sa.Column("password_hash", sa.String(512), nullable=True)
        )

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("messages"):
        op.create_table(
            "messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "sender_id",
                sa.String(64),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "recipient_id",
                sa.String(64),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("safety_result", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("read_at", sa.DateTime(timezone=True)),
        )
        op.create_index("ix_messages_sender_id", "messages", ["sender_id"])
        op.create_index("ix_messages_recipient_id", "messages", ["recipient_id"])
        op.create_index("ix_messages_created_at", "messages", ["created_at"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("messages"):
        op.drop_table("messages")
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "password_hash" in user_columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("password_hash")
