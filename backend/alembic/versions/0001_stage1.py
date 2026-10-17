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
    Base.metadata.create_all(bind=op.get_bind())

def downgrade():
    Base.metadata.drop_all(bind=op.get_bind())
