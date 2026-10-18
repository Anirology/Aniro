"""Google integration and AI usage metadata.

Revision ID: 0005_stage4_integrations
Revises: 0004_stage3_area_targets
"""
from alembic import op
from db import Base
import models

revision = "0005_stage4_integrations"
down_revision = "0004_stage3_area_targets"
branch_labels = None
depends_on = None

def upgrade():
    for name in ("google_integrations", "coach_usage"):
        Base.metadata.tables[name].create(op.get_bind())

def downgrade():
    for name in ("coach_usage", "google_integrations"):
        Base.metadata.tables[name].drop(op.get_bind())
