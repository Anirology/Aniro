"""Weekly planning, tasks, blocks, and explicit completion records.

Revision ID: 0002_stage2
Revises: 0001_stage1
"""
from alembic import op
from db import Base
import models

revision = "0002_stage2"
down_revision = "0001_stage1"
branch_labels = None
depends_on = None

OLD = "horizon IN ('10y','5y','2y','1y','3mo','month')"
NEW = "horizon IN ('10y','5y','2y','1y','3mo','month','week')"

def upgrade():
    with op.batch_alter_table("goals", recreate="always") as batch:
        batch.drop_constraint("goal_horizon", type_="check")
        batch.create_check_constraint("goal_horizon", NEW)
    for name in ("weekly_plans", "tasks", "calendar_blocks", "completion_logs"):
        Base.metadata.tables[name].create(op.get_bind())

def downgrade():
    for name in ("completion_logs", "calendar_blocks", "tasks", "weekly_plans"):
        Base.metadata.tables[name].drop(op.get_bind())
    with op.batch_alter_table("goals", recreate="always") as batch:
        batch.drop_constraint("goal_horizon", type_="check")
        batch.create_check_constraint("goal_horizon", OLD)
