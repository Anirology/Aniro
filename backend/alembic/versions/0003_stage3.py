"""Habits, reflections, budgets, and expenses.

Revision ID: 0003_stage3
Revises: 0002_stage2
"""
from alembic import op
from db import Base
import models

revision = "0003_stage3"
down_revision = "0002_stage2"
branch_labels = None
depends_on = None

TABLES = ("habits", "habit_checkins", "balance_targets", "reflect_settings", "budget_months", "expense_categories", "expenses")

def upgrade():
    for name in TABLES:
        Base.metadata.tables[name].create(op.get_bind())

def downgrade():
    for name in reversed(TABLES):
        Base.metadata.tables[name].drop(op.get_bind())
