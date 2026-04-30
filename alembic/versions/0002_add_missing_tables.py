"""Add missing tables for full backend functionality

Revision ID: 0002_add_missing_tables
Revises: 0001_phase2_baseline
Create Date: 2026-04-27 00:00:00

Tables added:
- parent_accounts (guardian/parent accounts)
- parent_learner_links (learner-parent relationships)
- lessons (CAPS-aligned lesson content)
- assessments (quizzes/tests)
- assessment_attempts (learner assessment attempts)
- reports (generated reports)
- dummy_data_points (test data for development)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_add_missing_tables"
down_revision = "0001_phase2_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Parent Accounts (Guardian/Parent accounts with encrypted PII)
    op.create_table(
        "parent_accounts",
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email_encrypted", sa.Text, unique=True, nullable=False),
        sa.Column("password_hash", sa.String(200), nullable=False),
        sa.Column("full_name_encrypted", sa.Text),
        sa.Column("is_verified", sa.Boolean, default=False),
        sa.Column("verification_token", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_parent_accounts_email", "parent_accounts", ["email_encrypted"])

    # Parent-Learner Links (Many-to-many relationship)
    op.create_table(
        "parent_learner_links",
        sa.Column("link_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("parent_accounts.parent_id", ondelete="CASCADE"), nullable=False),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("learners.learner_id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship", sa.String(20), default="guardian"),  # guardian, parent, grandparent
        sa.Column("is_verified", sa.Boolean, default=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_parent_learner_links_parent", "parent_learner_links", ["parent_id"])
    op.create_index("ix_parent_learner_links_learner", "parent_learner_links", ["learner_id"])

    # Lessons (CAPS-aligned lesson content)
    op.create_table(
        "lessons",
        sa.Column("lesson_id", sa.String(50), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("subject_code", sa.String(20), nullable=False),
        sa.Column("grade_level", sa.SmallInteger, nullable=False),
        sa.Column("unit", sa.String(50)),
        sa.Column("topic", sa.String(100)),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_modality", sa.String(20), default="text"),  # text, video, interactive
        sa.Column("duration_minutes", sa.SmallInteger, default=15),
        sa.Column("difficulty_level", sa.Float, default=0.5),
        sa.Column("learning_objectives", postgresql.JSON, default=[]),
        sa.Column("prerequisites", postgresql.JSON, default=[]),
        sa.Column("is_cap_aligned", sa.Boolean, default=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("version", sa.Integer, default=1),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("grade_level >= 0 AND grade_level <= 7", name="ck_lesson_grade"),
    )
    op.create_index("ix_lessons_subject_grade", "lessons", ["subject_code", "grade_level"])
    op.create_index("ix_lessons_topic", "lessons", ["topic"])

    # Assessments (Quizzes/Tests)
    op.create_table(
        "assessments",
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("subject_code", sa.String(20), nullable=False),
        sa.Column("grade_level", sa.SmallInteger, nullable=False),
        sa.Column("assessment_type", sa.String(30), nullable=False),  # quiz, test, exam, diagnostic
        sa.Column("total_marks", sa.Integer, default=0),
        sa.Column("time_limit_minutes", sa.SmallInteger),
        sa.Column("passing_score", sa.Float, default=0.5),
        sa.Column("questions", postgresql.JSON, nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("grade_level >= 0 AND grade_level <= 7", name="ck_assessment_grade"),
    )
    op.create_index("ix_assessments_subject_grade", "assessments", ["subject_code", "grade_level"])

    # Assessment Attempts (Learner attempts at assessments)
    op.create_table(
        "assessment_attempts",
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("learners.learner_id", ondelete="CASCADE"), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assessments.assessment_id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Float),
        sa.Column("marks_obtained", sa.Integer),
        sa.Column("time_taken_seconds", sa.Integer),
        sa.Column("responses", postgresql.JSON, default=[]),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_assessment_attempts_learner", "assessment_attempts", ["learner_id"])
    op.create_index("ix_assessment_attempts_assessment", "assessment_attempts", ["assessment_id"])

    # Reports (Generated reports for learners and guardians)
    op.create_table(
        "reports",
        sa.Column("report_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("learners.learner_id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_type", sa.String(30), nullable=False),  # progress, diagnostic, weekly, monthly, parent
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", postgresql.JSON, nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("generated_by", sa.String(50), default="SYSTEM"),
        sa.Column("is_shared", sa.Boolean, default=False),
        sa.Column("shared_with_guardian", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_reports_learner", "reports", ["learner_id"])
    op.create_index("ix_reports_type", "reports", ["report_type"])

    # Dummy Data Points (Test data for development)
    op.create_table(
        "dummy_data_points",
        sa.Column("data_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(50), nullable=False),  # learner, session, mastery, etc.
        sa.Column("payload", postgresql.JSON, nullable=False),
        sa.Column("is_persistent", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_dummy_data_points_kind_created", "dummy_data_points", ["kind", "created_at"])


def downgrade() -> None:
    op.drop_table("dummy_data_points")
    op.drop_table("reports")
    op.drop_table("assessment_attempts")
    op.drop_table("assessments")
    op.drop_table("lessons")
    op.drop_table("parent_learner_links")
    op.drop_table("parent_accounts")
