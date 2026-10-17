from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, ForeignKey, Integer, DateTime, Text, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db import Base

def uid(): return str(uuid4())
def now(): return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    display_name: Mapped[str] = mapped_column(String(120), default="Local user")
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Colombo")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class LifeArea(Base):
    __tablename__ = "life_areas"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    color_key: Mapped[str] = mapped_column(String(30), default="lime")
    icon_key: Mapped[str] = mapped_column(String(30), default="target")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tracks: Mapped[list["Track"]] = relationship(back_populates="area")

class Track(Base):
    __tablename__ = "tracks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    life_area_id: Mapped[str] = mapped_column(ForeignKey("life_areas.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    color_key: Mapped[str] = mapped_column(String(30), default="lime")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    area: Mapped[LifeArea] = relationship(back_populates="tracks")
    modules: Mapped[list["Module"]] = relationship(back_populates="track")

class Module(Base):
    __tablename__ = "modules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    track_id: Mapped[str] = mapped_column(ForeignKey("tracks.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="active")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    track: Mapped[Track] = relationship(back_populates="modules")

class Goal(Base):
    __tablename__ = "goals"
    __table_args__ = (CheckConstraint("horizon IN ('10y','5y','2y','1y','3mo','month','week')", name="goal_horizon"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    life_area_id: Mapped[str] = mapped_column(ForeignKey("life_areas.id"), index=True)
    track_id: Mapped[str | None] = mapped_column(ForeignKey("tracks.id"), index=True)
    module_id: Mapped[str | None] = mapped_column(ForeignKey("modules.id"), index=True)
    parent_goal_id: Mapped[str | None] = mapped_column(ForeignKey("goals.id"), index=True)
    horizon: Mapped[str] = mapped_column(String(10), index=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    target_date: Mapped[str | None] = mapped_column(String(10))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class WeeklyPlan(Base):
    __tablename__ = "weekly_plans"
    __table_args__ = (UniqueConstraint("user_id", "week_start", name="weekly_plan_user_week"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    week_start: Mapped[str] = mapped_column(String(10), index=True)
    capacity_minutes: Mapped[int | None] = mapped_column(Integer)
    seasonal_priority: Mapped[str | None] = mapped_column(String(240))

class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (CheckConstraint("status IN ('planned','done','partial','missed','moved')", name="task_status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    goal_id: Mapped[str | None] = mapped_column(ForeignKey("goals.id"), index=True)
    module_id: Mapped[str | None] = mapped_column(ForeignKey("modules.id"), index=True)
    week_start: Mapped[str] = mapped_column(String(10), index=True)
    title: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(20), default="planned")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estimate_minutes: Mapped[int | None] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class CalendarBlock(Base):
    __tablename__ = "calendar_blocks"
    __table_args__ = (CheckConstraint("status IN ('planned','done','partial','missed','moved')", name="block_status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(20), default="planned")
    google_event_id: Mapped[str | None] = mapped_column(String(200))
    sync_state: Mapped[str] = mapped_column(String(30), default="local")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class CompletionLog(Base):
    __tablename__ = "completion_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    calendar_block_id: Mapped[str | None] = mapped_column(ForeignKey("calendar_blocks.id"), index=True)
    completed_minutes: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[str] = mapped_column(String(20))
    note: Mapped[str] = mapped_column(Text, default="")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
