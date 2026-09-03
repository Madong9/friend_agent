"""Add partner request loop, notifications, personality and campus verification.

Revision ID: 0009_partner_loop_personality
Revises: 0008_add_wechat_and_mock_flags
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_partner_loop_personality"
down_revision = "0008_add_wechat_and_mock_flags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    additions = {
        "campus_verified": sa.Column(
            "campus_verified", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        "personality_consent": sa.Column(
            "personality_consent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        "personality_traits": sa.Column(
            "personality_traits", sa.JSON(), nullable=False, server_default="{}"
        ),
        "personality_summary": sa.Column(
            "personality_summary", sa.Text(), nullable=False, server_default=""
        ),
        "personality_updated_at": sa.Column(
            "personality_updated_at", sa.DateTime(timezone=True), nullable=True
        ),
    }
    for name, column in additions.items():
        if name not in user_columns:
            op.add_column("users", column)
    op.execute(
        "UPDATE users SET campus_verified = true "
        "WHERE school_email IS NOT NULL OR school_uid IS NOT NULL OR is_mock = true"
    )

    report_columns = {column["name"] for column in inspector.get_columns("reports")}
    if "category" not in report_columns:
        op.add_column(
            "reports",
            sa.Column(
                "category", sa.String(32), nullable=False, server_default="OTHER"
            ),
        )
        op.create_index("ix_reports_category", "reports", ["category"])

    if not inspector.has_table("partner_requests"):
        op.create_table(
            "partner_requests",
            sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
            sa.Column(
                "user_id",
                sa.String(64),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("session_id", sa.String(64), nullable=False, unique=True),
            sa.Column("intent", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("normalized_activity", sa.String(64), nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default="OPEN"),
            sa.Column("note", sa.Text(), nullable=False, server_default=""),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index("ix_partner_requests_user_id", "partner_requests", ["user_id"])
        op.create_index(
            "ix_partner_requests_session_id",
            "partner_requests",
            ["session_id"],
            unique=True,
        )
        op.create_index(
            "ix_partner_requests_normalized_activity",
            "partner_requests",
            ["normalized_activity"],
        )
        op.create_index(
            "ix_partner_requests_expires_at", "partner_requests", ["expires_at"]
        )

    if not inspector.has_table("notifications"):
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
            sa.Column(
                "user_id",
                sa.String(64),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("kind", sa.String(32), nullable=False),
            sa.Column("title", sa.String(128), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
        op.create_index("ix_notifications_kind", "notifications", ["kind"])
        op.create_index("ix_notifications_read_at", "notifications", ["read_at"])
        op.create_index("ix_notifications_created_at", "notifications", ["created_at"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("notifications"):
        op.drop_table("notifications")
    if inspector.has_table("partner_requests"):
        op.drop_table("partner_requests")
    report_columns = {column["name"] for column in inspector.get_columns("reports")}
    if "category" in report_columns:
        with op.batch_alter_table("reports") as batch_op:
            batch_op.drop_column("category")
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    with op.batch_alter_table("users") as batch_op:
        for name in (
            "personality_updated_at",
            "personality_summary",
            "personality_traits",
            "personality_consent",
            "campus_verified",
        ):
            if name in user_columns:
                batch_op.drop_column(name)
