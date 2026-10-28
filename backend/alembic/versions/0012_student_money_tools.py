"""Add accounts, essential envelopes, upcoming bills, and expense accounts.

Revision ID: 0012_student_money_tools
Revises: 0011_custom_recurrence
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_student_money_tools"
down_revision = "0011_custom_recurrence"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("financial_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("balance_minor", sa.Integer(), nullable=False),
        sa.Column("color_key", sa.String(30), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)))
    op.create_index("ix_financial_accounts_user_id", "financial_accounts", ["user_id"])
    op.create_table("expense_envelopes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("budget_month_id", sa.String(36), sa.ForeignKey("budget_months.id"), nullable=False),
        sa.Column("category_id", sa.String(36), sa.ForeignKey("expense_categories.id"), nullable=False),
        sa.Column("limit_minor", sa.Integer(), nullable=False),
        sa.Column("essential", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("budget_month_id", "category_id", name="envelope_budget_category"))
    op.create_index("ix_expense_envelopes_budget_month_id", "expense_envelopes", ["budget_month_id"])
    op.create_index("ix_expense_envelopes_category_id", "expense_envelopes", ["category_id"])
    op.create_table("upcoming_bills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("financial_accounts.id")),
        sa.Column("series_id", sa.String(36)),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("due_on", sa.String(10), nullable=False),
        sa.Column("recurring_monthly", sa.Boolean(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("series_id", "due_on", name="bill_series_due"))
    op.create_index("ix_upcoming_bills_user_id", "upcoming_bills", ["user_id"])
    op.create_index("ix_upcoming_bills_account_id", "upcoming_bills", ["account_id"])
    op.create_index("ix_upcoming_bills_series_id", "upcoming_bills", ["series_id"])
    op.create_index("ix_upcoming_bills_due_on", "upcoming_bills", ["due_on"])
    if op.get_bind().dialect.name == "sqlite":
        op.add_column("expenses", sa.Column("account_id", sa.String(36)))
    else:
        op.add_column("expenses", sa.Column("account_id", sa.String(36), sa.ForeignKey("financial_accounts.id")))
    op.create_index("ix_expenses_account_id", "expenses", ["account_id"])


def downgrade():
    op.drop_index("ix_expenses_account_id", "expenses")
    op.drop_column("expenses", "account_id")
    op.drop_table("upcoming_bills")
    op.drop_table("expense_envelopes")
    op.drop_table("financial_accounts")
