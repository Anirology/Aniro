"""Add income and account transfer ledger.

Revision ID: 0013_money_movements
Revises: 0012_student_money_tools
"""
from alembic import op
import sqlalchemy as sa


revision = "0013_money_movements"
down_revision = "0012_student_money_tools"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "money_movements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("source_account_id", sa.String(36), sa.ForeignKey("financial_accounts.id")),
        sa.Column("destination_account_id", sa.String(36), sa.ForeignKey("financial_accounts.id"), nullable=False),
        sa.Column("source_label", sa.String(120)),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("occurred_on", sa.String(10), nullable=False),
        sa.Column("note", sa.String(240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_money_movements_user_id", "money_movements", ["user_id"])
    op.create_index("ix_money_movements_kind", "money_movements", ["kind"])
    op.create_index("ix_money_movements_source_account_id", "money_movements", ["source_account_id"])
    op.create_index("ix_money_movements_destination_account_id", "money_movements", ["destination_account_id"])
    op.create_index("ix_money_movements_occurred_on", "money_movements", ["occurred_on"])


def downgrade():
    op.drop_table("money_movements")
