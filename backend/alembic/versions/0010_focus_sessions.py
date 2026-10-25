"""Persist focus preferences, work sessions, and linked completion logs.

Revision ID: 0010_focus_sessions
Revises: 0009_recurring_weekly_goals
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_focus_sessions"
down_revision = "0009_recurring_weekly_goals"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("focus_preferences",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("focus_minutes", sa.Integer(), nullable=False),
        sa.Column("short_break_minutes", sa.Integer(), nullable=False),
        sa.Column("long_break_minutes", sa.Integer(), nullable=False),
        sa.Column("long_break_every", sa.Integer(), nullable=False),
        sa.Column("sound", sa.Boolean(), nullable=False),
        sa.Column("auto_transitions", sa.Boolean(), nullable=False))
    op.create_table("focus_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id")),
        sa.Column("phase", sa.String(24), nullable=False),
        sa.Column("running", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("phase_started_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("remaining_seconds", sa.Integer(), nullable=False),
        sa.Column("accrued_seconds", sa.Integer(), nullable=False),
        sa.Column("gap_seconds", sa.Integer(), nullable=False),
        sa.Column("focus_intervals", sa.Integer(), nullable=False),
        sa.Column("next_action", sa.String(500), nullable=False),
        sa.Column("return_instruction", sa.String(500), nullable=False),
        sa.Column("return_phase", sa.String(24), nullable=False),
        sa.Column("return_seconds", sa.Integer(), nullable=False),
        sa.Column("distraction_note", sa.String(1000), nullable=False),
        sa.Column("learning_checked", sa.Boolean(), nullable=False),
        sa.Column("difficulty", sa.Boolean(), nullable=False),
        sa.Column("recorded_minutes", sa.Integer()),
        sa.Column("result_status", sa.String(20)),
        sa.Column("result_note", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)))
    op.create_index("ix_focus_sessions_user_id", "focus_sessions", ["user_id"])
    op.create_index("ix_focus_sessions_task_id", "focus_sessions", ["task_id"])
    op.create_index("focus_one_active_user", "focus_sessions", ["user_id"], unique=True,
                    postgresql_where=sa.text("ended_at IS NULL"), sqlite_where=sa.text("ended_at IS NULL"))
    if op.get_bind().dialect.name == "sqlite":
        op.add_column("completion_logs", sa.Column("focus_session_id", sa.String(36)))
    else:
        op.add_column("completion_logs", sa.Column("focus_session_id", sa.String(36), sa.ForeignKey("focus_sessions.id")))
    op.create_index("ix_completion_logs_focus_session_id", "completion_logs", ["focus_session_id"], unique=True)


def downgrade():
    op.drop_index("ix_completion_logs_focus_session_id", "completion_logs")
    op.drop_column("completion_logs", "focus_session_id")
    op.drop_index("focus_one_active_user", "focus_sessions")
    op.drop_index("ix_focus_sessions_task_id", "focus_sessions")
    op.drop_index("ix_focus_sessions_user_id", "focus_sessions")
    op.drop_table("focus_sessions")
    op.drop_table("focus_preferences")
