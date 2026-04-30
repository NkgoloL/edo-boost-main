"""
alembic/versions/0001_initial_consolidated_schema.py

Consolidated initial migration.  This single revision absorbs everything
previously spread across:
  - scripts/db_init.sql
  - scripts/db_audit_migration.sql

Seed *data* (db_seed.sql) does NOT belong in a migration — it is handled
by scripts/db_seed.sql run once via the db-migrate service after this
migration completes.

Run with:
    alembic upgrade head
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extensions ────────────────────────────────────────────────────────
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # ── Enums ─────────────────────────────────────────────────────────────
    consent_status = postgresql.ENUM(
        "pending", "granted", "revoked", "expired",
        name="consent_status_enum",
        create_type=True,
    )
    consent_status.create(op.get_bind(), checkfirst=True)

    learner_grade = postgresql.ENUM(
        "R", "1", "2", "3", "4", "5", "6", "7",
        name="grade_enum",
        create_type=True,
    )
    learner_grade.create(op.get_bind(), checkfirst=True)

    audit_action = postgresql.ENUM(
        "create", "read", "update", "delete",
        "consent_granted", "consent_revoked", "erasure_requested", "erasure_completed",
        "llm_call", "login", "logout",
        name="audit_action_enum",
        create_type=True,
    )
    audit_action.create(op.get_bind(), checkfirst=True)

    # ── guardians (parents / legal guardians) ─────────────────────────────
    op.create_table(
        "guardians",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("email_hash", sa.Text, nullable=False, unique=True,
                  comment="SHA-256 of lowercased email — never store raw email"),
        sa.Column("encrypted_email", sa.Text, nullable=False,
                  comment="pgcrypto-encrypted email for contact purposes"),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("phone_hash", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True,
                  comment="Soft-delete for right-to-erasure workflow"),
    )
    op.create_index("ix_guardians_email_hash", "guardians", ["email_hash"])

    # ── learners ──────────────────────────────────────────────────────────
    op.create_table(
        "learners",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("pseudonym_id", sa.Text, nullable=False, unique=True,
                  comment="Random opaque ID passed to LLM providers — never the real UUID"),
        sa.Column("guardian_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("grade", sa.Enum("R", "1", "2", "3", "4", "5", "6", "7",
                                    name="grade_enum", create_type=False),
                  nullable=False),
        sa.Column("date_of_birth", sa.Date, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["guardian_id"], ["guardians.id"],
                                name="fk_learners_guardian",
                                ondelete="RESTRICT"),
    )
    op.create_index("ix_learners_guardian_id", "learners", ["guardian_id"])
    op.create_index("ix_learners_pseudonym_id", "learners", ["pseudonym_id"])

    # ── parental_consents ─────────────────────────────────────────────────
    op.create_table(
        "parental_consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("guardian_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Enum("pending", "granted", "revoked", "expired",
                                     name="consent_status_enum", create_type=False),
                  nullable=False, server_default="pending"),
        sa.Column("granted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True,
                  comment="Annual renewal: set to granted_at + 1 year"),
        sa.Column("ip_address", sa.Text, nullable=True,
                  comment="Hashed — for audit purposes only"),
        sa.Column("user_agent_hash", sa.Text, nullable=True),
        sa.Column("consent_version", sa.Text, nullable=False, server_default="1.0",
                  comment="Version of the consent wording shown to the guardian"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"],
                                name="fk_consents_learner", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["guardian_id"], ["guardians.id"],
                                name="fk_consents_guardian", ondelete="CASCADE"),
        sa.UniqueConstraint("learner_id", "guardian_id",
                            name="uq_consent_learner_guardian"),
    )
    op.create_index("ix_consents_learner_id", "parental_consents", ["learner_id"])
    op.create_index("ix_consents_status", "parental_consents", ["status"])

    # ── diagnostic_sessions ───────────────────────────────────────────────
    op.create_table(
        "diagnostic_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("grade_assessed", sa.Text, nullable=False),
        sa.Column("subject", sa.Text, nullable=False),
        sa.Column("irt_theta", sa.Float, nullable=True),
        sa.Column("knowledge_gaps", postgresql.JSONB, nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"],
                                name="fk_diagnostic_learner", ondelete="CASCADE"),
    )
    op.create_index("ix_diagnostic_learner_id", "diagnostic_sessions", ["learner_id"])

    # ── study_plans ───────────────────────────────────────────────────────
    op.create_table(
        "study_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("diagnostic_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("plan_data", postgresql.JSONB, nullable=False),
        sa.Column("caps_week", sa.Integer, nullable=True),
        sa.Column("active", sa.Boolean, server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["learner_id"], ["learners.id"],
                                name="fk_study_plan_learner", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["diagnostic_session_id"], ["diagnostic_sessions.id"],
                                name="fk_study_plan_diagnostic", ondelete="SET NULL"),
    )

    # ── audit_log ─────────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("action", sa.Enum(
            "create", "read", "update", "delete",
            "consent_granted", "consent_revoked",
            "erasure_requested", "erasure_completed",
            "llm_call", "login", "logout",
            name="audit_action_enum", create_type=False),
            nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True,
                  comment="Guardian or learner who triggered the event"),
        sa.Column("target_table", sa.Text, nullable=True),
        sa.Column("target_id", sa.Text, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("ip_hash", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_actor_id", "audit_log", ["actor_id"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    # ── Row-level updated_at trigger ──────────────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION trigger_set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    for table in ("guardians", "learners", "parental_consents", "study_plans"):
        op.execute(f"""
            CREATE TRIGGER set_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE PROCEDURE trigger_set_updated_at();
        """)


def downgrade() -> None:
    for table in ("guardians", "learners", "parental_consents", "study_plans"):
        op.execute(f"DROP TRIGGER IF EXISTS set_updated_at ON {table}")
    op.execute("DROP FUNCTION IF EXISTS trigger_set_updated_at()")

    op.drop_table("audit_log")
    op.drop_table("study_plans")
    op.drop_table("diagnostic_sessions")
    op.drop_table("parental_consents")
    op.drop_table("learners")
    op.drop_table("guardians")

    op.execute("DROP TYPE IF EXISTS audit_action_enum")
    op.execute("DROP TYPE IF EXISTS consent_status_enum")
    op.execute("DROP TYPE IF EXISTS grade_enum")
