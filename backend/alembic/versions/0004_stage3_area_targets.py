"""Area-level weekly balance targets.

Revision ID: 0004_stage3_area_targets
Revises: 0003_stage3
"""
from alembic import op
from db import Base
import models

revision = "0004_stage3_area_targets"
down_revision = "0003_stage3"
branch_labels = None
depends_on = None

def upgrade():
    Base.metadata.tables["area_balance_targets"].create(op.get_bind())

def downgrade():
    Base.metadata.tables["area_balance_targets"].drop(op.get_bind())
