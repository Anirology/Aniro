"""Add per-module recurring weekly goal templates.

Revision ID: 0009_recurring_weekly_goals
Revises: 0008_backup_snapshots
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_recurring_weekly_goals"
down_revision = "0008_backup_snapshots"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "recurring_weekly_goals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("module_id", sa.String(36), sa.ForeignKey("modules.id"), nullable=False),
        sa.Column("starts_on", sa.String(10), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "module_id", name="recurring_goal_user_module"),
    )
    op.create_index("ix_recurring_weekly_goals_user_id", "recurring_weekly_goals", ["user_id"])
    op.create_index("ix_recurring_weekly_goals_module_id", "recurring_weekly_goals", ["module_id"])
    # SQLite cannot add a foreign key constraint to an existing table without
    # rebuilding it; the nullable column is enough for the local database.
    if op.get_bind().dialect.name == "sqlite":
        op.add_column("goals", sa.Column("recurring_template_id", sa.String(36)))
    else:
        op.add_column("goals", sa.Column("recurring_template_id", sa.String(36), sa.ForeignKey("recurring_weekly_goals.id")))
    op.create_index("ix_goals_recurring_template_id", "goals", ["recurring_template_id"])
    op.create_index("recurring_goal_template_week", "goals", ["recurring_template_id", "target_date"], unique=True)


def downgrade():
    op.drop_index("recurring_goal_template_week", "goals")
    op.drop_index("ix_goals_recurring_template_id", "goals")
    op.drop_column("goals", "recurring_template_id")
    op.drop_index("ix_recurring_weekly_goals_module_id", "recurring_weekly_goals")
    op.drop_index("ix_recurring_weekly_goals_user_id", "recurring_weekly_goals")
    op.drop_table("recurring_weekly_goals")
