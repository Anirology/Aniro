"""Stage 1 goal hierarchy

Revision ID: 0001_stage1
Revises:
"""
from alembic import op
from db import Base
import models

revision = "0001_stage1"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create only the foundational tables. Later revisions add their own tables.
    # Vision is included because the current weekly-goal schema references it.
    for name in ("users", "life_areas", "tracks", "modules", "visions", "goals"):
        Base.metadata.tables[name].create(op.get_bind())

def downgrade():
    for name in ("goals", "visions", "modules", "tracks", "life_areas", "users"):
        Base.metadata.tables[name].drop(op.get_bind())
