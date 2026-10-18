"""Add an editable three-year goal horizon.

Revision ID: 0006_three_year_goals
Revises: 0005_stage4_integrations
"""
from alembic import op

revision = "0006_three_year_goals"
down_revision = "0005_stage4_integrations"
branch_labels = None
depends_on = None

OLD = "horizon IN ('10y','5y','2y','1y','3mo','month','week')"
NEW = "horizon IN ('10y','5y','3y','2y','1y','3mo','month','week')"


def upgrade():
    with op.batch_alter_table("goals", recreate="always") as batch:
        batch.drop_constraint("goal_horizon", type_="check")
        batch.create_check_constraint("goal_horizon", NEW)


def downgrade():
    with op.batch_alter_table("goals", recreate="always") as batch:
        batch.drop_constraint("goal_horizon", type_="check")
        batch.create_check_constraint("goal_horizon", OLD)
