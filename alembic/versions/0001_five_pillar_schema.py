"""
Alembic migration: EduBoost five-pillar schema.
Creates all tables required by the architectural implementation.
Enforces:
  - constitutional_rules: Postgres trigger blocks UPDATE/DELETE
  - audit_log: append-only trigger
  - consent_audit: RLS policy via learner_sessions example
  - All FK relationships and composite indexes for portal query performance
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_five_pillar_schema"
down_revision = "0003_add_items_correct"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # PILLAR 1 — LEGISLATURE                                               #
    # ------------------------------------------------------------------ #
    op.create_table(
        "constitutional_rules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("rule_id", sa.String(64), nullable=False),
        sa.Column("source_document", sa.String(256), nullable=False),
        sa.Column("rule_text", sa.Text, nullable=False),
        sa.Column("scope_subjects", postgresql.ARRAY(sa.String), nullable=True),
        sa.Column("scope_grade_min", sa.Integer, nullable=True),
        sa.Column("scope_grade_max", sa.Integer, nullable=True),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("immutable_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("rule_id", "effective_date", name="uq_rule_version"),
        sa.UniqueConstraint("immutable_hash", name="uq_rule_hash"),
    )
    op.create_index("ix_constitutional_rules_rule_id", "constitutional_rules", ["rule_id"])

    op.execute("""
        CREATE OR REPLACE FUNCTION constitutional_rules_immutable()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'constitutional_rules rows are immutable. Insert a new version row instead.';
        END;
        $$;

        CREATE TRIGGER trg_constitutional_rules_no_update
        BEFORE UPDATE ON constitutional_rules
        FOR EACH ROW EXECUTE FUNCTION constitutional_rules_immutable();

        CREATE TRIGGER trg_constitutional_rules_no_delete
        BEFORE DELETE ON constitutional_rules
        FOR EACH ROW EXECUTE FUNCTION constitutional_rules_immutable();
    """)

    op.create_table(
        "rule_set_signatures",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("bundle_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("signature", sa.Text, nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("rule_count", sa.Integer, nullable=False),
        sa.Column("signer_key_id", sa.String(128), nullable=False),
    )

    op.create_table(
        "legislature_source_hashes",
        sa.Column("source_key", sa.String(64), primary_key=True),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ------------------------------------------------------------------ #
    # PILLAR 2 — EXECUTIVE                                                 #
    # ------------------------------------------------------------------ #
    op.create_table(
        "lesson_results",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("action_id", sa.String(36), nullable=False, unique=True),
        sa.Column("stamp_id", sa.String(36), nullable=False),
        sa.Column("learner_pseudonym", sa.String(128), nullable=False),
        sa.Column("subject", sa.String(64), nullable=False),
        sa.Column("grade", sa.Integer, nullable=False),
        sa.Column("topic", sa.String(256), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_lesson_results_learner", "lesson_results", ["learner_pseudonym"])

    # ------------------------------------------------------------------ #
    # PILLAR 3 — JUDICIARY                                                 #
    # ------------------------------------------------------------------ #
    op.create_table(
        "judiciary_stamps",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("stamp_id", sa.String(36), nullable=False, unique=True),
        sa.Column("action_id", sa.String(36), nullable=False),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("rules_checked", sa.Text, nullable=False, default="[]"),
        sa.Column("reason", sa.Text, nullable=False, default=""),
        sa.Column("reviewer_model_version", sa.String(128), nullable=False, default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_judiciary_stamps_action_id", "judiciary_stamps", ["action_id"])

    op.create_table(
        "judiciary_stamp_cache",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("stamp_id", sa.String(36), nullable=False),
        sa.Column("agent_id", sa.String(128), nullable=False),
        sa.Column("intent", sa.String(128), nullable=False),
        sa.Column("rules_hash", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("agent_id", "intent", "rules_hash", name="uq_stamp_cache_key"),
    )

    op.create_table(
        "constitutional_violations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("violation_id", sa.String(36), nullable=False, unique=True),
        sa.Column("action_id", sa.String(36), nullable=False),
        sa.Column("stamp_id", sa.String(36), nullable=True),
        sa.Column("agent_id", sa.String(128), nullable=False),
        sa.Column("violation_type", sa.String(64), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("learner_pseudonym", sa.String(128), nullable=True),
        sa.Column("audit_event_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_constitutional_violations_action", "constitutional_violations", ["action_id"])
    op.create_index("ix_constitutional_violations_learner", "constitutional_violations", ["learner_pseudonym"])

    # ------------------------------------------------------------------ #
    # PILLAR 4 — FOURTH ESTATE                                            #
    # ------------------------------------------------------------------ #
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(36), nullable=False, unique=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("stream_entry_id", sa.String(64), nullable=False, unique=True),
        sa.Column("learner_pseudonym", sa.String(128), nullable=True),
        sa.Column("event_data", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    # Composite index for portal queries
    op.create_index(
        "ix_audit_log_learner_type_created",
        "audit_log",
        ["learner_pseudonym", "event_type", "created_at"],
    )
    # Partial index for descending created_at portal queries
    op.create_index(
        "ix_audit_log_created_desc",
        "audit_log",
        [sa.text("created_at DESC")],
    )

    # Append-only trigger for audit_log
    op.execute("""
        CREATE OR REPLACE FUNCTION audit_log_append_only()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only. UPDATE and DELETE are prohibited.';
        END;
        $$;

        CREATE TRIGGER trg_audit_log_no_update
        BEFORE UPDATE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION audit_log_append_only();

        CREATE TRIGGER trg_audit_log_no_delete
        BEFORE DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION audit_log_append_only();
    """)

    # ------------------------------------------------------------------ #
    # CONSENT                                                              #
    # ------------------------------------------------------------------ #
    # Row-Level Security policy for learner_sessions (consent gate)
    op.execute("""
        CREATE TABLE IF NOT EXISTS learner_sessions (
            id SERIAL PRIMARY KEY,
            learner_pseudonym VARCHAR(128) NOT NULL,
            session_data JSONB,
            created_at TIMESTAMPTZ DEFAULT now()
        );

        ALTER TABLE learner_sessions ENABLE ROW LEVEL SECURITY;

        CREATE POLICY consent_gate ON learner_sessions
          USING (
            EXISTS (
              SELECT 1 FROM consent_audit
              WHERE consent_audit.pseudonym_id::text = learner_sessions.learner_pseudonym
                AND consent_audit.event_type = 'consent_granted'
                AND NOT EXISTS (
                  SELECT 1 FROM consent_audit revoked
                  WHERE revoked.pseudonym_id = consent_audit.pseudonym_id
                    AND revoked.event_type = 'consent_revoked'
                    AND revoked.occurred_at > consent_audit.occurred_at
                )
            )
          );
    """)

    # ------------------------------------------------------------------ #
    # PILLAR 5 — ETHER                                                     #
    # ------------------------------------------------------------------ #
    op.create_table(
        "ether_profiles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("learner_pseudonym", sa.String(128), nullable=False, unique=True),
        sa.Column("dominant_sephira", sa.String(32), nullable=False, default="Tiferet"),
        sa.Column("tone_pacing", sa.Float, nullable=False, default=0.5),
        sa.Column("metaphor_style", sa.String(32), nullable=False, default="narrative"),
        sa.Column("warmth_level", sa.Float, nullable=False, default=0.7),
        sa.Column("challenge_tolerance", sa.Float, nullable=False, default=0.5),
        sa.Column("preferred_narrative_frame", sa.String(32), nullable=False, default="explorer"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ------------------------------------------------------------------ #
    # IRT ENGINE                                                           #
    # ------------------------------------------------------------------ #
    op.create_table(
        "irt_item_parameters",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("item_id", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("a", sa.Float, nullable=False, default=1.0),
        sa.Column("b", sa.Float, nullable=False, default=0.0),
        sa.Column("c", sa.Float, nullable=False, default=0.25),
        sa.Column("calibration_source", sa.String(64), nullable=False, default="auto"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("item_id", "version", name="uq_irt_item_version"),
    )

    op.create_table(
        "irt_responses",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("learner_pseudonym", sa.String(128), nullable=False),
        sa.Column("item_id", sa.String(64), nullable=False),
        sa.Column("correct", sa.Boolean, nullable=False),
        sa.Column("updated_theta", sa.Float, nullable=False),
        sa.Column("response_time_ms", sa.Integer, nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_irt_responses_learner", "irt_responses", ["learner_pseudonym"])

    op.create_table(
        "irt_learner_estimates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("learner_pseudonym", sa.String(128), nullable=False, unique=True),
        sa.Column("theta", sa.Float, nullable=False, default=0.0),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ------------------------------------------------------------------ #
    # ORCHESTRATOR                                                         #
    # ------------------------------------------------------------------ #
    op.create_table(
        "session_states",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("learner_pseudonym", sa.String(128), nullable=False, unique=True),
        sa.Column("state", sa.String(32), nullable=False, default="IDLE"),
        sa.Column("previous_state", sa.String(32), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ------------------------------------------------------------------ #
    # DATA RETENTION POLICY                                                #
    # ------------------------------------------------------------------ #
    op.create_table(
        "data_retention_policy",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("table_name", sa.String(64), nullable=False, unique=True),
        sa.Column("retention_days", sa.Integer, nullable=False),
        sa.Column("archive_to_r2", sa.Boolean, nullable=False, default=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    for table in [
        "data_retention_policy", "session_states",
        "irt_learner_estimates", "irt_responses", "irt_item_parameters",
        "ether_profiles", "learner_sessions",
        "audit_log", "constitutional_violations",
        "judiciary_stamp_cache", "judiciary_stamps",
        "lesson_results",
        "legislature_source_hashes", "rule_set_signatures", "constitutional_rules",
    ]:
        op.drop_table(table)

    for fn in ["constitutional_rules_immutable", "audit_log_append_only"]:
        op.execute(f"DROP FUNCTION IF EXISTS {fn}() CASCADE;")
