"""Add RLHF pipeline tables

Revision ID: 0004_add_rlhf_pipeline
Revises: 0003_add_items_correct
Create Date: 2026-05-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_add_rlhf_pipeline"
down_revision = "0003_add_items_correct"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── lesson_feedback ──────────────────────────────────────────────────────
    op.create_table(
        "lesson_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("lesson_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True),
        sa.Column("learner_pseudonym", sa.Text, nullable=False),
        sa.Column("rating", sa.SmallInteger, nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("subject", sa.Text, nullable=True),
        sa.Column("grade_level", sa.SmallInteger, nullable=True),
        sa.Column("language_code", sa.String(8), server_default="en", nullable=False),
        sa.Column("prompt_version", sa.Text, nullable=True),
        sa.Column("submitted_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("exported_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_feedback_lesson_id", "lesson_feedback", ["lesson_id"])
    op.create_index("ix_feedback_exported_at", "lesson_feedback", ["exported_at"])

    # ── rlhf_exports ─────────────────────────────────────────────────────────
    op.create_table(
        "rlhf_exports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("format", sa.Text, nullable=False),
        sa.Column("language_code", sa.String(8), nullable=True),
        sa.Column("positive_count", sa.Integer, nullable=False),
        sa.Column("negative_count", sa.Integer, nullable=False),
        sa.Column("record_count", sa.Integer, nullable=False),
        sa.Column("dataset_json", sa.Text, nullable=False),
        sa.Column("exported_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("rlhf_exports")
    op.drop_table("lesson_feedback")
