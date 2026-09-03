"""Add WeChat identity and mock-user flags.

Revision ID: 0008_add_wechat_and_mock_flags
Revises: 0007_repair_legacy_profile
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_add_wechat_and_mock_flags"
down_revision = "0007_repair_legacy_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("users"):
        return
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "wechat_openid" not in columns:
        op.add_column(
            "users", sa.Column("wechat_openid", sa.String(128), nullable=True)
        )
        op.create_index(
            "ix_users_wechat_openid", "users", ["wechat_openid"], unique=True
        )
    if "is_mock" not in columns:
        op.add_column(
            "users",
            sa.Column(
                "is_mock", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
        )
    if "updated_at" not in columns:
        op.add_column(
            "users", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("users"):
        return
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "updated_at" in columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("updated_at")
    if "is_mock" in columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("is_mock")
    if "wechat_openid" in columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("wechat_openid")
