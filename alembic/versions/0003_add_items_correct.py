"""Add items_correct to DiagnosticSession

Revision ID: 0003_add_items_correct
Revises: 0002_add_missing_tables
Create Date: 2026-04-28 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_add_items_correct"
down_revision = "0002_add_missing_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "diagnostic_sessions",
        sa.Column("items_correct", sa.Integer, nullable=True, server_default="0"),
    )
    op.create_index("ix_diagnostic_sessions_learner", "diagnostic_sessions", ["learner_id"]) 


def downgrade() -> None:
    op.drop_index("ix_diagnostic_sessions_learner", table_name="diagnostic_sessions")
    op.drop_column("diagnostic_sessions", "items_correct")
