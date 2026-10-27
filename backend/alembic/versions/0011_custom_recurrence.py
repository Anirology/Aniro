"""Add daily and weekly recurrence to goals and tasks.

Revision ID: 0011_custom_recurrence
Revises: 0010_focus_sessions
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_custom_recurrence"
down_revision = "0010_focus_sessions"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("goals", "tasks"):
        op.add_column(table, sa.Column("recurrence_id", sa.String(36)))
        op.add_column(table, sa.Column("recurrence_frequency", sa.String(10)))
        op.add_column(table, sa.Column("occurrence_date", sa.String(10)))
        op.create_index(f"ix_{table}_recurrence_id", table, ["recurrence_id"])
        op.create_index(f"{table}_recurrence_occurrence", table,
                        ["recurrence_id", "occurrence_date"], unique=True)


def downgrade():
    for table in ("tasks", "goals"):
        op.drop_index(f"{table}_recurrence_occurrence", table)
        op.drop_index(f"ix_{table}_recurrence_id", table)
        for column in ("occurrence_date", "recurrence_frequency", "recurrence_id"):
            op.drop_column(table, column)
