"""Add school identity and token revocation support.

Revision ID: 0003_add_school_identity_and_token_revocation
Revises: 0002_add_auth_and_messages
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_add_school_identity_and_token_revocation"
down_revision = "0002_add_auth_and_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "school_email" not in user_columns:
        op.add_column("users", sa.Column("school_email", sa.String(128), nullable=True))
        op.create_index("ix_users_school_email", "users", ["school_email"], unique=True)
    if "identity_provider" not in user_columns:
        op.add_column(
            "users",
            sa.Column(
                "identity_provider",
                sa.String(32),
                nullable=False,
                server_default="email",
            ),
        )
    if "token_version" not in user_columns:
        op.add_column(
            "users",
            sa.Column(
                "token_version", sa.Integer(), nullable=False, server_default="0"
            ),
        )
    if "last_token_revoked_at" not in user_columns:
        op.add_column(
            "users",
            sa.Column(
                "last_token_revoked_at", sa.DateTime(timezone=True), nullable=True
            ),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "last_token_revoked_at" in user_columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("last_token_revoked_at")
    if "token_version" in user_columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("token_version")
    if "identity_provider" in user_columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("identity_provider")
    if "school_email" in user_columns:
        op.drop_index("ix_users_school_email", table_name="users")
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("school_email")
