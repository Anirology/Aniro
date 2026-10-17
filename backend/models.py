from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, ForeignKey, Integer, DateTime, Text, CheckConstraint
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
    __table_args__ = (CheckConstraint("horizon IN ('10y','5y','2y','1y','3mo','month')", name="goal_horizon"),)
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
