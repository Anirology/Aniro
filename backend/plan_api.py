from datetime import date, datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from db import SessionLocal
from models import User, LifeArea, Track, Module, Goal, WeeklyPlan, Task, CalendarBlock, CompletionLog

router = APIRouter(prefix="/api")
Status = Literal["planned", "done", "partial", "missed", "moved"]

def session():
    with SessionLocal() as db: yield db

def current_user(db: Session):
    u = db.scalar(select(User).limit(1))
    if not u:
        u = User()
        db.add(u)
        db.commit()
        db.refresh(u)
    return u

def obj(db: Session, cls, id: str):
    item = db.get(cls, id)
    if not item: raise HTTPException(404, "Record not found")
    return item

def owner_task(db: Session, id: str):
    task = obj(db, Task, id)
    if task.user_id != current_user(db).id: raise HTTPException(404, "Record not found")
    return task

def owner_block(db: Session, id: str):
    block = obj(db, CalendarBlock, id)
    owner_task(db, block.task_id)
    return block

def encoded(item):
    result = {}
    for column in item.__table__.columns:
        value = getattr(item, column.name)
        if isinstance(value, datetime):
            value = value.replace(tzinfo=timezone.utc).isoformat() if value.tzinfo is None else value.astimezone(timezone.utc).isoformat()
        result[column.name] = value
    return result

def commit(db: Session, item):
    db.add(item)
    db.commit()
    db.refresh(item)
    return encoded(item)

def week_date(value: str):
    try: day = date.fromisoformat(value)
    except ValueError: raise HTTPException(422, "Use YYYY-MM-DD for week start")
    if day.weekday() != 0: raise HTTPException(422, "Week start must be Monday")
    return day

def utc_naive(value: datetime):
    if value.tzinfo is None: raise HTTPException(422, "Time must include a timezone offset")
    return value.astimezone(timezone.utc).replace(tzinfo=None)

def hierarchy(db: Session, goal: Goal):
    area = obj(db, LifeArea, goal.life_area_id)
    track = obj(db, Track, goal.track_id) if goal.track_id else None
    module = obj(db, Module, goal.module_id) if goal.module_id else None
    return {
        "breadcrumb": " → ".join([x.name for x in (area, track, module) if x]),
        "color_key": track.color_key if track else area.color_key,
        "area_name": area.name,
        "track_name": track.name if track else None,
        "module_name": module.name if module else None,
    }

def completion_totals(db: Session, user_id: str, week_start: str):
    tasks = list(db.scalars(select(Task).where(Task.user_id == user_id, Task.week_start == week_start)))
    task_ids = [task.id for task in tasks]
    if not task_ids:
        return {"planned_minutes": 0, "completed_minutes": 0, "completed_tasks": 0}
    blocks = list(db.scalars(select(CalendarBlock).where(CalendarBlock.task_id.in_(task_ids), CalendarBlock.archived_at.is_(None))))
    logs = list(db.scalars(select(CompletionLog).where(CompletionLog.task_id.in_(task_ids))))
    return {
        "planned_minutes": sum(round((b.end_at - b.start_at).total_seconds() / 60) for b in blocks),
        "completed_minutes": sum(log.completed_minutes for log in logs if log.result in ("done", "partial")),
        "completed_tasks": sum(task.status == "done" for task in tasks),
    }

class WeeklySettingsIn(BaseModel):
    capacity_minutes: int | None = Field(default=None, ge=0, le=10080)
    seasonal_priority: str | None = Field(default=None, max_length=240)

class TimezoneIn(BaseModel):
    timezone: str = Field(min_length=1, max_length=80)

class TaskIn(BaseModel):
    goal_id: str | None = None
    module_id: str | None = None
    week_start: str
    title: str = Field(min_length=1, max_length=240)
    due_at: datetime | None = None
    estimate_minutes: int | None = Field(default=None, ge=0, le=10080)
    sort_order: int = 0

class BlockIn(BaseModel):
    task_id: str
    start_at: datetime
    end_at: datetime

class ResultIn(BaseModel):
    status: Status
    actual_minutes: int | None = Field(default=None, ge=0, le=10080)
    note: str = Field(default="", max_length=2000)

def validate_task(db: Session, data: TaskIn):
    week_date(data.week_start)
    u = current_user(db)
    goal = None
    if data.goal_id:
        goal = obj(db, Goal, data.goal_id)
        if goal.user_id != u.id or goal.horizon != "week" or goal.target_date != data.week_start or goal.archived_at:
            raise HTTPException(422, "Task must link to an active goal in this week")
        if goal.module_id and not data.module_id:
            data.module_id = goal.module_id
    if data.module_id:
        module = obj(db, Module, data.module_id)
        track = obj(db, Track, module.track_id)
        area = obj(db, LifeArea, track.life_area_id)
        if area.user_id != u.id or module.archived_at or track.archived_at or area.archived_at:
            raise HTTPException(422, "Module is unavailable")
        if goal and (goal.module_id and goal.module_id != module.id or goal.track_id and goal.track_id != track.id or goal.life_area_id != area.id):
            raise HTTPException(422, "Module does not match goal hierarchy")
    if goal and goal.module_id and data.module_id and goal.module_id != data.module_id:
        raise HTTPException(422, "Module does not match goal")

def task_values(data: TaskIn):
    return {**data.model_dump(exclude={"due_at"}), "due_at": utc_naive(data.due_at) if data.due_at else None}

def validate_block(db: Session, data: BlockIn, own_id: str | None = None):
    task = owner_task(db, data.task_id)
    if task.archived_at: raise HTTPException(422, "Restore task before scheduling")
    start, end = utc_naive(data.start_at), utc_naive(data.end_at)
    if end <= start: raise HTTPException(422, "End time must follow start time")
    if end - start > timedelta(hours=24): raise HTTPException(422, "A block cannot exceed 24 hours")
    overlaps = db.scalar(select(CalendarBlock.id).join(Task).where(
        Task.user_id == task.user_id, CalendarBlock.archived_at.is_(None),
        CalendarBlock.start_at < end, CalendarBlock.end_at > start,
        CalendarBlock.id != own_id if own_id else CalendarBlock.id.is_not(None),
    ).limit(1))
    if overlaps: raise HTTPException(409, "This time overlaps another block. Choose a free time.")
    return start, end

def replace_log(db: Session, task_id: str, block_id: str | None, status: Status, minutes: int, note: str):
    old = list(db.scalars(select(CompletionLog).where(CompletionLog.task_id == task_id, CompletionLog.calendar_block_id == block_id) if block_id else select(CompletionLog).where(CompletionLog.task_id == task_id, CompletionLog.calendar_block_id.is_(None))))
    for log in old: db.delete(log)
    if status in ("done", "partial"):
        db.add(CompletionLog(task_id=task_id, calendar_block_id=block_id, completed_minutes=minutes, result=status, note=note))

def block_task_status(db: Session, task: Task):
    statuses = [b.status for b in db.scalars(select(CalendarBlock).where(CalendarBlock.task_id == task.id, CalendarBlock.archived_at.is_(None)))]
    if not statuses: return task.status
    if all(s == "done" for s in statuses): return "done"
    if any(s in ("done", "partial") for s in statuses): return "partial"
    if all(s == "missed" for s in statuses): return "missed"
    if all(s == "moved" for s in statuses): return "moved"
    return "planned"

@router.get("/plan")
def plan(week: str, db: Session = Depends(session)):
    week_date(week)
    u = current_user(db)
    areas = list(db.scalars(select(LifeArea).where(LifeArea.user_id == u.id).order_by(LifeArea.sort_order, LifeArea.name)))
    area_ids = [a.id for a in areas]
    tracks = list(db.scalars(select(Track).where(Track.life_area_id.in_(area_ids)))) if area_ids else []
    track_ids = [t.id for t in tracks]
    modules = list(db.scalars(select(Module).where(Module.track_id.in_(track_ids)))) if track_ids else []
    all_goals = list(db.scalars(select(Goal).where(Goal.user_id == u.id)))
    goals = [g for g in all_goals if g.horizon == "week" and g.target_date == week]
    tasks = list(db.scalars(select(Task).where(Task.user_id == u.id, Task.week_start == week).order_by(Task.sort_order, Task.title)))
    task_ids = [t.id for t in tasks]
    blocks = list(db.scalars(select(CalendarBlock).where(CalendarBlock.task_id.in_(task_ids)).order_by(CalendarBlock.start_at))) if task_ids else []
    logs = list(db.scalars(select(CompletionLog).where(CompletionLog.task_id.in_(task_ids)))) if task_ids else []
    settings = db.scalar(select(WeeklyPlan).where(WeeklyPlan.user_id == u.id, WeeklyPlan.week_start == week))
    return {
        "timezone": u.timezone,
        "areas": [encoded(x) for x in areas], "tracks": [encoded(x) for x in tracks], "modules": [encoded(x) for x in modules],
        "goals": [{**encoded(g), **hierarchy(db, g)} for g in goals],
        "long_goals": [{**encoded(g), **hierarchy(db, g)} for g in all_goals if g.horizon != "week" and not g.archived_at],
        "tasks": [encoded(x) for x in tasks], "blocks": [encoded(x) for x in blocks], "logs": [encoded(x) for x in logs],
        "settings": encoded(settings) if settings else {"capacity_minutes": None, "seasonal_priority": None},
        "totals": completion_totals(db, u.id, week),
    }

@router.put("/plan/{week}/settings")
def save_week_settings(week: str, data: WeeklySettingsIn, db: Session = Depends(session)):
    week_date(week)
    u = current_user(db)
    settings = db.scalar(select(WeeklyPlan).where(WeeklyPlan.user_id == u.id, WeeklyPlan.week_start == week))
    if not settings: settings = WeeklyPlan(user_id=u.id, week_start=week)
    settings.capacity_minutes = data.capacity_minutes
    settings.seasonal_priority = data.seasonal_priority or None
    return commit(db, settings)

@router.put("/plan/timezone")
def save_timezone(data: TimezoneIn, db: Session = Depends(session)):
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(data.timezone)
    except Exception: raise HTTPException(422, "Use a valid IANA timezone, such as Asia/Colombo")
    u = current_user(db)
    u.timezone = data.timezone
    return commit(db, u)

@router.post("/tasks", status_code=201)
def add_task(data: TaskIn, db: Session = Depends(session)):
    validate_task(db, data)
    return commit(db, Task(user_id=current_user(db).id, **task_values(data)))

@router.put("/tasks/{id}")
def edit_task(id: str, data: TaskIn, db: Session = Depends(session)):
    task = owner_task(db, id)
    validate_task(db, data)
    if task.week_start != data.week_start and db.scalar(select(CalendarBlock.id).where(CalendarBlock.task_id == id).limit(1)):
        raise HTTPException(409, "Move or remove scheduled blocks before changing the task week")
    for key, value in task_values(data).items(): setattr(task, key, value)
    return commit(db, task)

@router.post("/tasks/{id}/archive")
def archive_task(id: str, restore: bool = False, db: Session = Depends(session)):
    task = owner_task(db, id)
    task.archived_at = None if restore else datetime.now(timezone.utc)
    return commit(db, task)

@router.delete("/tasks/{id}")
def delete_task(id: str, confirm: bool = Query(False), db: Session = Depends(session)):
    if not confirm: raise HTTPException(400, "Deletion requires confirmation")
    task = owner_task(db, id)
    if db.scalar(select(CalendarBlock.id).where(CalendarBlock.task_id == id).limit(1)) or db.scalar(select(CompletionLog.id).where(CompletionLog.task_id == id).limit(1)):
        raise HTTPException(409, "Task has schedule or history. Archive it instead.")
    db.delete(task)
    db.commit()
    return {"deleted": True}

@router.post("/tasks/{id}/result")
def task_result(id: str, data: ResultIn, db: Session = Depends(session)):
    task = owner_task(db, id)
    if task.archived_at: raise HTTPException(422, "Restore task first")
    if data.status == "partial" and not (data.actual_minutes or data.note.strip()):
        raise HTTPException(422, "Partial work needs actual minutes or a note")
    for log in db.scalars(select(CompletionLog).where(CompletionLog.task_id == id)):
        db.delete(log)
    for block in db.scalars(select(CalendarBlock).where(CalendarBlock.task_id == id, CalendarBlock.archived_at.is_(None))):
        block.status = data.status
    task.status = data.status
    if data.status in ("done", "partial"):
        minutes = data.actual_minutes if data.actual_minutes is not None else (task.estimate_minutes or 0) if data.status == "done" else 0
        db.add(CompletionLog(task_id=id, completed_minutes=minutes, result=data.status, note=data.note))
    db.commit()
    db.refresh(task)
    return {"task": encoded(task), "totals": completion_totals(db, task.user_id, task.week_start)}

@router.post("/calendar-blocks", status_code=201)
def add_block(data: BlockIn, db: Session = Depends(session)):
    start, end = validate_block(db, data)
    return commit(db, CalendarBlock(task_id=data.task_id, start_at=start, end_at=end))

@router.put("/calendar-blocks/{id}")
def edit_block(id: str, data: BlockIn, db: Session = Depends(session)):
    block = owner_block(db, id)
    if block.task_id != data.task_id and db.scalar(select(CompletionLog.id).where(CompletionLog.calendar_block_id == id).limit(1)):
        raise HTTPException(409, "Completed block cannot move to another task")
    start, end = validate_block(db, data, id)
    block.task_id, block.start_at, block.end_at = data.task_id, start, end
    return commit(db, block)

@router.post("/calendar-blocks/{id}/result")
def block_result(id: str, data: ResultIn, db: Session = Depends(session)):
    block = owner_block(db, id)
    task = owner_task(db, block.task_id)
    if block.archived_at or task.archived_at: raise HTTPException(422, "Restore the block and task first")
    if data.status == "partial" and not (data.actual_minutes or data.note.strip()):
        raise HTTPException(422, "Partial work needs actual minutes or a note")
    block.status = data.status
    for direct in db.scalars(select(CompletionLog).where(CompletionLog.task_id == task.id, CompletionLog.calendar_block_id.is_(None))):
        db.delete(direct)
    minutes = data.actual_minutes if data.actual_minutes is not None else round((block.end_at - block.start_at).total_seconds() / 60) if data.status == "done" else 0
    replace_log(db, task.id, id, data.status, minutes, data.note)
    db.flush()
    task.status = block_task_status(db, task)
    db.commit()
    return {"block": encoded(block), "task": encoded(task), "totals": completion_totals(db, task.user_id, task.week_start)}

@router.post("/calendar-blocks/{id}/archive")
def archive_block(id: str, restore: bool = False, db: Session = Depends(session)):
    block = owner_block(db, id)
    block.archived_at = None if restore else datetime.now(timezone.utc)
    return commit(db, block)

@router.delete("/calendar-blocks/{id}")
def delete_block(id: str, confirm: bool = Query(False), db: Session = Depends(session)):
    if not confirm: raise HTTPException(400, "Deletion requires confirmation")
    block = owner_block(db, id)
    if db.scalar(select(CompletionLog.id).where(CompletionLog.calendar_block_id == id).limit(1)):
        raise HTTPException(409, "Block has completion history. Archive it instead.")
    db.delete(block)
    db.commit()
    return {"deleted": True}
