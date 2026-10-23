"""Store a recoverable JSON snapshot before hosted restores.

Revision ID: 0008_backup_snapshots
Revises: 0007_visions
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_backup_snapshots"
down_revision = "0007_visions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "backup_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
    )


def downgrade():
    op.drop_table("backup_snapshots")
