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

class Vision(Base):
    __tablename__ = "visions"
    __table_args__ = (CheckConstraint("horizon IN ('10y','5y','3y','2y','1y','3mo','month')", name="vision_horizon"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    life_area_id: Mapped[str] = mapped_column(ForeignKey("life_areas.id"), index=True)
    track_id: Mapped[str | None] = mapped_column(ForeignKey("tracks.id"), index=True)
    module_id: Mapped[str | None] = mapped_column(ForeignKey("modules.id"), index=True)
    parent_vision_id: Mapped[str | None] = mapped_column(ForeignKey("visions.id"), index=True)
    horizon: Mapped[str] = mapped_column(String(10), index=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    target_date: Mapped[str | None] = mapped_column(String(10))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class Goal(Base):
    __tablename__ = "goals"
    __table_args__ = (CheckConstraint("horizon = 'week'", name="goal_horizon"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    life_area_id: Mapped[str] = mapped_column(ForeignKey("life_areas.id"), index=True)
    track_id: Mapped[str | None] = mapped_column(ForeignKey("tracks.id"), index=True)
    module_id: Mapped[str | None] = mapped_column(ForeignKey("modules.id"), index=True)
    parent_vision_id: Mapped[str | None] = mapped_column(ForeignKey("visions.id"), index=True)
    horizon: Mapped[str] = mapped_column(String(10), default="week", index=True)
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

class Habit(Base):
    __tablename__ = "habits"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    life_area_id: Mapped[str] = mapped_column(ForeignKey("life_areas.id"), index=True)
    track_id: Mapped[str | None] = mapped_column(ForeignKey("tracks.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    frequency_rule: Mapped[str] = mapped_column(String(20), default="daily")
    color_key: Mapped[str] = mapped_column(String(30), default="lime")
    created_on: Mapped[str] = mapped_column(String(10))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class HabitCheckin(Base):
    __tablename__ = "habit_checkins"
    __table_args__ = (UniqueConstraint("habit_id", "local_date", name="habit_day_unique"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    habit_id: Mapped[str] = mapped_column(ForeignKey("habits.id"), index=True)
    local_date: Mapped[str] = mapped_column(String(10), index=True)
    status: Mapped[str] = mapped_column(String(20), default="done")

class BalanceTarget(Base):
    __tablename__ = "balance_targets"
    __table_args__ = (UniqueConstraint("user_id", "track_id", name="balance_user_track"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    track_id: Mapped[str] = mapped_column(ForeignKey("tracks.id"), index=True)
    target_minutes: Mapped[int] = mapped_column(Integer)

class ReflectSettings(Base):
    __tablename__ = "reflect_settings"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    coach_trigger_count: Mapped[int] = mapped_column(Integer, default=2)

class AreaBalanceTarget(Base):
    __tablename__ = "area_balance_targets"
    __table_args__ = (UniqueConstraint("user_id", "life_area_id", name="balance_user_area"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    life_area_id: Mapped[str] = mapped_column(ForeignKey("life_areas.id"), index=True)
    target_minutes: Mapped[int] = mapped_column(Integer)

class BudgetMonth(Base):
    __tablename__ = "budget_months"
    __table_args__ = (UniqueConstraint("user_id", "year", "month", name="budget_user_month"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="LKR")
    limit_minor: Mapped[int] = mapped_column(Integer)

class ExpenseCategory(Base):
    __tablename__ = "expense_categories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    color_key: Mapped[str] = mapped_column(String(30), default="lime")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class Expense(Base):
    __tablename__ = "expenses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    budget_month_id: Mapped[str] = mapped_column(ForeignKey("budget_months.id"), index=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("expense_categories.id"), index=True)
    amount_minor: Mapped[int] = mapped_column(Integer)
    spent_on: Mapped[str] = mapped_column(String(10), index=True)
    description: Mapped[str] = mapped_column(String(240), default="")

class GoogleIntegration(Base):
    __tablename__ = "google_integrations"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    account_email: Mapped[str | None] = mapped_column(String(240))
    selected_calendar_id: Mapped[str | None] = mapped_column(String(240))
    encrypted_token: Mapped[str | None] = mapped_column(Text)
    oauth_state: Mapped[str | None] = mapped_column(String(120))
    code_verifier: Mapped[str | None] = mapped_column(String(160))
    oauth_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(500))

class CoachUsage(Base):
    __tablename__ = "coach_usage"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    prompt_version: Mapped[str] = mapped_column(String(20), default="prd-v1")
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)

class BackupSnapshot(Base):
    __tablename__ = "backup_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    payload: Mapped[str] = mapped_column(Text)
