"""Create the original MVP schema when missing; preserve existing databases.

Revision ID: 0001_existing_schema_baseline
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_existing_schema_baseline"
down_revision = None
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("nickname", sa.String(64), nullable=False),
            sa.Column("school", sa.String(128), nullable=False),
            sa.Column("campus", sa.String(64), nullable=False),
            sa.Column("grade", sa.String(32), nullable=False),
            sa.Column("major", sa.String(128), nullable=False),
            sa.Column("bio", sa.Text(), nullable=False),
            sa.Column("social_goals", sa.JSON(), nullable=False),
            sa.Column("interests", sa.JSON(), nullable=False),
            sa.Column("activities", sa.JSON(), nullable=False),
            sa.Column("availability", sa.JSON(), nullable=False),
            sa.Column("social_style", sa.String(64), nullable=False),
            sa.Column("avoidances", sa.JSON(), nullable=False),
            sa.Column("recommendation_enabled", sa.Boolean(), nullable=False),
            sa.Column("verified", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    if not _has_table("activities"):
        op.create_table(
            "activities",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("campus", sa.String(64), nullable=False),
            sa.Column("location", sa.String(128), nullable=False),
            sa.Column("time", sa.String(128), nullable=False),
            sa.Column("tags", sa.JSON(), nullable=False),
            sa.Column("capacity", sa.Integer(), nullable=False),
            sa.Column("public", sa.Boolean(), nullable=False),
        )
    if not _has_table("preferences"):
        op.create_table(
            "preferences",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.String(64),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("key", sa.String(128), nullable=False),
            sa.Column("value", sa.String(255), nullable=False),
            sa.Column("weight", sa.Float(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("user_id", "key", name="uq_preference_user_key"),
        )
        op.create_index("ix_preferences_user_id", "preferences", ["user_id"])
        op.create_index("ix_preferences_key", "preferences", ["key"])
    if not _has_table("interactions"):
        op.create_table(
            "interactions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "actor_id",
                sa.String(64),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "target_id",
                sa.String(64),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
            ),
            sa.Column("kind", sa.String(32), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_interactions_actor_id", "interactions", ["actor_id"])
        op.create_index("ix_interactions_target_id", "interactions", ["target_id"])
        op.create_index("ix_interactions_kind", "interactions", ["kind"])
        op.create_index("ix_interactions_created_at", "interactions", ["created_at"])
    if not _has_table("matches"):
        op.create_table(
            "matches",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_a_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.Column(
                "user_b_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("score", sa.Float()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("user_a_id", "user_b_id", name="uq_match_pair"),
        )
        op.create_index("ix_matches_user_a_id", "matches", ["user_a_id"])
        op.create_index("ix_matches_user_b_id", "matches", ["user_b_id"])
    if not _has_table("blocks"):
        op.create_table(
            "blocks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "blocker_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.Column(
                "blocked_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("blocker_id", "blocked_id", name="uq_block_direction"),
        )
        op.create_index("ix_blocks_blocker_id", "blocks", ["blocker_id"])
        op.create_index("ix_blocks_blocked_id", "blocks", ["blocked_id"])
    if not _has_table("reports"):
        op.create_table(
            "reports",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "reporter_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.Column(
                "reported_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_reports_reporter_id", "reports", ["reporter_id"])
        op.create_index("ix_reports_reported_id", "reports", ["reported_id"])


def downgrade() -> None:
    # The baseline may have adopted an existing database, so destructive downgrade is unsafe.
    pass
