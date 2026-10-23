"""Move Clarity horizons into visions; reserve goals for weekly outcomes.

Revision ID: 0007_visions
Revises: 0006_three_year_goals
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_visions"
down_revision = "0006_three_year_goals"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("visions"):
        op.create_table(
            "visions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("life_area_id", sa.String(36), sa.ForeignKey("life_areas.id"), nullable=False),
            sa.Column("track_id", sa.String(36), sa.ForeignKey("tracks.id")),
            sa.Column("module_id", sa.String(36), sa.ForeignKey("modules.id")),
            sa.Column("parent_vision_id", sa.String(36), sa.ForeignKey("visions.id")),
            sa.Column("horizon", sa.String(10), nullable=False),
            sa.Column("title", sa.String(240), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("target_date", sa.String(10)),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("archived_at", sa.DateTime(timezone=True)),
            sa.CheckConstraint("horizon IN ('10y','5y','3y','2y','1y','3mo','month')", name="vision_horizon"),
        )
        for field in ("user_id", "life_area_id", "track_id", "module_id", "parent_vision_id", "horizon"):
            op.create_index(f"ix_visions_{field}", "visions", [field])

    columns = {c["name"] for c in sa.inspect(bind).get_columns("goals")}
    if "parent_vision_id" not in columns:
        op.add_column("goals", sa.Column("parent_vision_id", sa.String(36)))
        op.create_index("ix_goals_parent_vision_id", "goals", ["parent_vision_id"])
    if "parent_goal_id" in columns:
        bad = bind.execute(sa.text("SELECT COUNT(*) FROM tasks WHERE goal_id IN (SELECT id FROM goals WHERE horizon <> 'week')")).scalar_one()
        if bad:
            raise RuntimeError("A task links to a long-term record; resolve it before migrating")
        bind.execute(sa.text("""
            INSERT INTO visions (id,user_id,life_area_id,track_id,module_id,parent_vision_id,horizon,title,description,status,target_date,sort_order,archived_at)
            SELECT id,user_id,life_area_id,track_id,module_id,parent_goal_id,horizon,title,description,status,target_date,sort_order,archived_at
            FROM goals WHERE horizon <> 'week'
            ORDER BY CASE horizon WHEN '10y' THEN 0 WHEN '5y' THEN 1 WHEN '3y' THEN 2 WHEN '2y' THEN 3 WHEN '1y' THEN 4 WHEN '3mo' THEN 5 ELSE 6 END
        """))
        bind.execute(sa.text("UPDATE goals SET parent_vision_id=parent_goal_id WHERE horizon='week'"))
        bind.execute(sa.text("UPDATE goals SET parent_goal_id=NULL WHERE parent_goal_id IS NOT NULL"))
        bind.execute(sa.text("DELETE FROM goals WHERE horizon <> 'week'"))
        op.drop_index("ix_goals_parent_goal_id", table_name="goals")
        with op.batch_alter_table("goals", recreate="always") as batch:
            batch.drop_column("parent_goal_id")
            batch.drop_constraint("goal_horizon", type_="check")
            batch.create_check_constraint("goal_horizon", "horizon = 'week'")
            batch.create_foreign_key("fk_goals_parent_vision_id_visions", "visions", ["parent_vision_id"], ["id"])
    else:
        # A fresh database already has the final columns from model metadata.
        with op.batch_alter_table("goals", recreate="always") as batch:
            batch.drop_constraint("goal_horizon", type_="check")
            batch.create_check_constraint("goal_horizon", "horizon = 'week'")


def downgrade():
    raise RuntimeError("Vision migration is intentionally irreversible; restore a database backup to revert")
