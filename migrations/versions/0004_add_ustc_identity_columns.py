"""Add USTC identity columns.

Revision ID: 0004_add_ustc_identity_columns
Revises: 0003_add_school_identity_and_token_revocation
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_add_ustc_identity_columns"
down_revision = "0003_add_school_identity_and_token_revocation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "school_uid" not in user_columns:
        op.add_column("users", sa.Column("school_uid", sa.String(64), nullable=True))
        op.create_index("ix_users_school_uid", "users", ["school_uid"], unique=True)
    if "school_display_name" not in user_columns:
        op.add_column(
            "users", sa.Column("school_display_name", sa.String(128), nullable=True)
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "school_display_name" in user_columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("school_display_name")
    if "school_uid" in user_columns:
        op.drop_index("ix_users_school_uid", table_name="users")
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("school_uid")
