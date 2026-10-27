from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from db import SessionLocal
from models import User, LifeArea, Track, Module, Vision, Goal, RecurringWeeklyGoal, WeeklyPlan, Task, CalendarBlock, CompletionLog

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

def hierarchy(db: Session, goal: Goal | Vision):
    area = obj(db, LifeArea, goal.life_area_id)
    track = obj(db, Track, goal.track_id) if goal.track_id else None
    module = obj(db, Module, goal.module_id) if goal.module_id else None
    breadcrumb = " → ".join([x.name for x in (area, track, module) if x])
    if isinstance(goal, Goal) and goal.occurrence_date:
        day = date.fromisoformat(goal.occurrence_date).strftime("%a, %b %d")
        breadcrumb += f" · {day} · {goal.recurrence_frequency}"
    return {
        "breadcrumb": breadcrumb,
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
        "completed_minutes": sum(log.completed_minutes for log in logs if log.result in ("done", "partial", "working")),
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
    recurrence_frequency: Literal["daily", "weekly"] | None = None

class BlockIn(BaseModel):
    task_id: str
    start_at: datetime
    end_at: datetime

class TaskBlockIn(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    goal_id: str | None = None
    module_id: str | None = None
    week_start: str
    start_at: datetime
    end_at: datetime

class ResultIn(BaseModel):
    status: Status
    actual_minutes: int | None = Field(default=None, ge=0, le=10080)
    note: str = Field(default="", max_length=2000)

class QuickTaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=240)

class ReviewItemIn(BaseModel):
    block_id: str
    status: Literal["done", "missed"]

class ReviewIn(BaseModel):
    items: list[ReviewItemIn] = Field(min_length=1, max_length=100)

class RecurringGoalsIn(BaseModel):
    week_start: str
    module_ids: list[str] = Field(min_length=1, max_length=30)

class GoalCompletionIn(BaseModel):
    completed: bool

def recurring_goal_copy(module_name: str):
    return f"Finish this week’s {module_name} learning log", "Capture what you covered this week. Add a task only when there’s a specific next step."

def materialize_recurring_goals(db: Session, user_id: str, week: str):
    templates = list(db.scalars(select(RecurringWeeklyGoal).where(
        RecurringWeeklyGoal.user_id == user_id,
        RecurringWeeklyGoal.archived_at.is_(None),
        RecurringWeeklyGoal.starts_on <= week,
    )))
    changed = False
    for template in templates:
        module = db.get(Module, template.module_id)
        if not module or module.archived_at or module.status != "active": continue
        track = db.get(Track, module.track_id)
        if not track or track.archived_at: continue
        area = db.get(LifeArea, track.life_area_id)
        if not area or area.archived_at or area.user_id != user_id: continue
        existing = db.scalar(select(Goal).where(Goal.recurring_template_id == template.id, Goal.target_date == week))
        if existing: continue
        # An existing module goal becomes this week's instance, preserving its tasks and wording.
        existing = db.scalar(select(Goal).where(
            Goal.user_id == user_id, Goal.module_id == module.id,
            Goal.target_date == week, Goal.recurring_template_id.is_(None),
            Goal.archived_at.is_(None),
        ).order_by(Goal.sort_order, Goal.id))
        if existing:
            existing.recurring_template_id = template.id
            changed = True
            continue
        title, description = recurring_goal_copy(module.name)
        try:
            with db.begin_nested():
                db.add(Goal(user_id=user_id, life_area_id=area.id, track_id=track.id,
                            module_id=module.id, recurring_template_id=template.id,
                            target_date=week, title=title, description=description))
                db.flush()
            changed = True
        except IntegrityError:
            # Another request generated the same week concurrently.
            pass
    if changed: db.commit()

@router.post("/plan/recurring-goals", status_code=201)
def add_recurring_goals(data: RecurringGoalsIn, db: Session = Depends(session)):
    week_date(data.week_start)
    user = current_user(db)
    module_ids = list(dict.fromkeys(data.module_ids))
    for module_id in module_ids:
        module = db.get(Module, module_id)
        if not module: raise HTTPException(422, "Choose an active module")
        track = db.get(Track, module.track_id)
        area = db.get(LifeArea, track.life_area_id) if track else None
        if not area or area.user_id != user.id or area.archived_at or track.archived_at or module.archived_at or module.status != "active":
            raise HTTPException(422, "Choose an active module")
    for module_id in module_ids:
        template = db.scalar(select(RecurringWeeklyGoal).where(RecurringWeeklyGoal.user_id == user.id, RecurringWeeklyGoal.module_id == module_id))
        if template:
            template.archived_at = None
            template.starts_on = min(template.starts_on, data.week_start)
        else:
            db.add(RecurringWeeklyGoal(user_id=user.id, module_id=module_id, starts_on=data.week_start))
    db.commit()
    materialize_recurring_goals(db, user.id, data.week_start)
    return {"module_ids": module_ids}

@router.post("/plan/recurring-goals/{template_id}/stop")
def stop_recurring_goal(template_id: str, db: Session = Depends(session)):
    template = db.get(RecurringWeeklyGoal, template_id)
    if not template or template.user_id != current_user(db).id: raise HTTPException(404, "Recurring goal not found")
    template.archived_at = datetime.now(timezone.utc)
    return commit(db, template)

@router.post("/plan/goals/{goal_id}/completion")
def complete_weekly_goal(goal_id: str, data: GoalCompletionIn, db: Session = Depends(session)):
    goal = db.get(Goal, goal_id)
    if not goal or goal.user_id != current_user(db).id or goal.archived_at or goal.horizon != "week":
        raise HTTPException(404, "Weekly goal not found")
    goal.status = "completed" if data.completed else "active"
    return commit(db, goal)

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
    return {**data.model_dump(exclude={"due_at", "recurrence_frequency"}), "due_at": utc_naive(data.due_at) if data.due_at else None}


def occurrence_days(start: str, week: str, frequency: str):
    first, monday = date.fromisoformat(start), week_date(week)
    return [day.isoformat() for offset in range(7) if (day := monday + timedelta(days=offset)) >= first
            and (frequency == "daily" or day.weekday() == first.weekday())]


def set_recurrence(db: Session, item: Goal | Task, frequency: str | None, start: str | None):
    if item.recurring_template_id if isinstance(item, Goal) else False:
        if frequency: raise HTTPException(422, "This module goal already has its own weekly repeat")
        return
    if frequency and not start:
        raise HTTPException(422, "Choose a start date for recurrence")
    if frequency and not item.recurrence_id:
        db.flush()
        item.recurrence_id = item.id
        item.occurrence_date = start
    if item.recurrence_id:
        source = db.get(type(item), item.recurrence_id)
        if source:
            source.recurrence_frequency = frequency
            if frequency:
                fields = ("title", "description", "life_area_id", "track_id", "module_id", "parent_vision_id", "sort_order") if isinstance(item, Goal) else ("title", "module_id", "estimate_minutes", "sort_order")
                for field in fields: setattr(source, field, getattr(item, field))
            db.execute(update(type(item)).where(type(item).recurrence_id == item.recurrence_id).values(recurrence_frequency=frequency))
        item.recurrence_frequency = frequency


def materialize_custom_recurrences(db: Session, user_id: str, week: str):
    for cls in (Goal, Task):
        sources = list(db.scalars(select(cls).where(cls.user_id == user_id, cls.recurrence_frequency.is_not(None), cls.id == cls.recurrence_id)))
        for source in sources:
            for day in occurrence_days(source.occurrence_date, week, source.recurrence_frequency):
                if db.scalar(select(cls.id).where(cls.recurrence_id == source.id, cls.occurrence_date == day).limit(1)): continue
                if cls is Goal:
                    instance = Goal(user_id=user_id, life_area_id=source.life_area_id, track_id=source.track_id,
                                    module_id=source.module_id, parent_vision_id=source.parent_vision_id,
                                    title=source.title, description=source.description, target_date=week,
                                    sort_order=source.sort_order, recurrence_id=source.id,
                                    recurrence_frequency=source.recurrence_frequency, occurrence_date=day)
                else:
                    linked_goal = db.get(Goal, source.goal_id) if source.goal_id else None
                    match = db.scalar(select(Goal).where(Goal.recurrence_id == linked_goal.recurrence_id,
                        Goal.occurrence_date == day).limit(1)) if linked_goal and linked_goal.recurrence_id else None
                    if linked_goal and linked_goal.target_date == week: match = linked_goal
                    due = None
                    if source.due_at:
                        local = source.due_at.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(current_user(db).timezone))
                        due = utc_naive(datetime.combine(date.fromisoformat(day), local.timetz()))
                    instance = Task(user_id=user_id, goal_id=match.id if match else None,
                                    module_id=source.module_id, week_start=week, title=source.title,
                                    due_at=due, estimate_minutes=source.estimate_minutes, sort_order=source.sort_order,
                                    recurrence_id=source.id, recurrence_frequency=source.recurrence_frequency,
                                    occurrence_date=day)
                db.add(instance)
        db.flush()
    db.commit()

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
    old = list(db.scalars(select(CompletionLog).where(CompletionLog.task_id == task_id, CompletionLog.calendar_block_id == block_id) if block_id else select(CompletionLog).where(CompletionLog.task_id == task_id, CompletionLog.calendar_block_id.is_(None), CompletionLog.focus_session_id.is_(None))))
    for log in old: db.delete(log)
    if status in ("done", "partial"):
        db.add(CompletionLog(task_id=task_id, calendar_block_id=block_id, completed_minutes=minutes, result=status, note=note))

def has_recorded_focus(db: Session, task_id: str):
    return db.scalar(select(CompletionLog.id).where(CompletionLog.task_id == task_id,
                    CompletionLog.focus_session_id.is_not(None), CompletionLog.completed_minutes > 0).limit(1)) is not None

def block_task_status(db: Session, task: Task):
    focus_results = list(db.scalars(select(CompletionLog.result).where(CompletionLog.task_id == task.id, CompletionLog.focus_session_id.is_not(None))))
    if "done" in focus_results: return "done"
    statuses = [b.status for b in db.scalars(select(CalendarBlock).where(CalendarBlock.task_id == task.id, CalendarBlock.archived_at.is_(None)))]
    if not statuses: return "partial" if "partial" in focus_results else task.status
    if all(s == "done" for s in statuses): return "done"
    if any(s in ("done", "partial") for s in statuses): return "partial"
    if all(s == "missed" for s in statuses): return "missed"
    if all(s == "moved" for s in statuses): return "moved"
    return "partial" if "partial" in focus_results else "planned"

@router.get("/plan")
def plan(week: str, db: Session = Depends(session)):
    week_date(week)
    u = current_user(db)
    materialize_recurring_goals(db, u.id, week)
    materialize_custom_recurrences(db, u.id, week)
    areas = list(db.scalars(select(LifeArea).where(LifeArea.user_id == u.id).order_by(LifeArea.sort_order, LifeArea.name)))
    area_ids = [a.id for a in areas]
    tracks = list(db.scalars(select(Track).where(Track.life_area_id.in_(area_ids)))) if area_ids else []
    track_ids = [t.id for t in tracks]
    modules = list(db.scalars(select(Module).where(Module.track_id.in_(track_ids)))) if track_ids else []
    recurring_templates = list(db.scalars(select(RecurringWeeklyGoal).where(RecurringWeeklyGoal.user_id == u.id)))
    goals = list(db.scalars(select(Goal).where(Goal.user_id == u.id, Goal.target_date == week)))
    visions = list(db.scalars(select(Vision).where(Vision.user_id == u.id, Vision.archived_at.is_(None))))
    tasks = list(db.scalars(select(Task).where(Task.user_id == u.id, Task.week_start == week).order_by(Task.sort_order, Task.title)))
    task_ids = [t.id for t in tasks]
    blocks = list(db.scalars(select(CalendarBlock).where(CalendarBlock.task_id.in_(task_ids)).order_by(CalendarBlock.start_at))) if task_ids else []
    logs = list(db.scalars(select(CompletionLog).where(CompletionLog.task_id.in_(task_ids)))) if task_ids else []
    settings = db.scalar(select(WeeklyPlan).where(WeeklyPlan.user_id == u.id, WeeklyPlan.week_start == week))
    return {
        "timezone": u.timezone,
        "areas": [encoded(x) for x in areas], "tracks": [encoded(x) for x in tracks], "modules": [encoded(x) for x in modules],
        "recurring_templates": [encoded(x) for x in recurring_templates],
        "goals": [{**encoded(g), **hierarchy(db, g)} for g in goals],
        "visions": [{**encoded(v), **hierarchy(db, v)} for v in visions],
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
    task = Task(user_id=current_user(db).id, **task_values(data))
    db.add(task)
    if data.recurrence_frequency:
        start = data.due_at.astimezone(ZoneInfo(current_user(db).timezone)).date().isoformat() if data.due_at else data.week_start
        set_recurrence(db, task, data.recurrence_frequency, start)
    return commit(db, task)

@router.post("/tasks/quick", status_code=201)
def quick_task(data: QuickTaskIn, db: Session = Depends(session)):
    user = current_user(db)
    if not data.title.strip(): raise HTTPException(422, "Enter a task")
    local_day = datetime.now(ZoneInfo(user.timezone)).date()
    week = (local_day - timedelta(days=local_day.weekday())).isoformat()
    return commit(db, Task(user_id=user.id, week_start=week, title=data.title.strip()))

@router.post("/tasks/{id}/carryover", status_code=201)
def carryover_task(id: str, week: str, db: Session = Depends(session)):
    target = week_date(week)
    source = owner_task(db, id)
    if source.archived_at or source.status in ("done", "moved"):
        raise HTTPException(409, "Only unfinished active tasks can carry over")
    if target <= week_date(source.week_start):
        raise HTTPException(422, "Choose a later week")
    copied = Task(user_id=source.user_id, week_start=week, title=source.title,
                  module_id=source.module_id, estimate_minutes=source.estimate_minutes,
                  sort_order=source.sort_order)
    db.add(copied)
    source.status = "moved"
    for block in db.scalars(select(CalendarBlock).where(CalendarBlock.task_id == source.id, CalendarBlock.archived_at.is_(None))):
        if block.status in ("planned", "partial"):
            block.status = "moved"
    db.commit()
    db.refresh(copied)
    return {"task": encoded(copied), "source": encoded(source)}

@router.put("/tasks/{id}")
def edit_task(id: str, data: TaskIn, db: Session = Depends(session)):
    task = owner_task(db, id)
    validate_task(db, data)
    if task.week_start != data.week_start and db.scalar(select(CalendarBlock.id).where(CalendarBlock.task_id == id).limit(1)):
        raise HTTPException(409, "Move or remove scheduled blocks before changing the task week")
    title_changed = task.title != data.title
    for key, value in task_values(data).items(): setattr(task, key, value)
    start = task.occurrence_date or data.week_start
    set_recurrence(db, task, data.recurrence_frequency, start)
    if title_changed:
        for block in db.scalars(select(CalendarBlock).where(CalendarBlock.task_id == id, CalendarBlock.google_event_id.is_not(None))):
            if block.sync_state != "imported": block.sync_state = "pending_update"
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
    for log in db.scalars(select(CompletionLog).where(CompletionLog.task_id == id, CompletionLog.focus_session_id.is_(None))):
        db.delete(log)
    for block in db.scalars(select(CalendarBlock).where(CalendarBlock.task_id == id, CalendarBlock.archived_at.is_(None))):
        block.status = data.status
    task.status = data.status
    if data.status in ("done", "partial"):
        minutes = data.actual_minutes if data.actual_minutes is not None else (task.estimate_minutes or 0) if data.status == "done" and not has_recorded_focus(db, id) else 0
        db.add(CompletionLog(task_id=id, completed_minutes=minutes, result=data.status, note=data.note))
    db.commit()
    db.refresh(task)
    return {"task": encoded(task), "totals": completion_totals(db, task.user_id, task.week_start)}

@router.post("/calendar-blocks", status_code=201)
def add_block(data: BlockIn, db: Session = Depends(session)):
    start, end = validate_block(db, data)
    return commit(db, CalendarBlock(task_id=data.task_id, start_at=start, end_at=end))

@router.post("/task-blocks", status_code=201)
def add_task_block(data: TaskBlockIn, db: Session = Depends(session)):
    minutes = round((utc_naive(data.end_at) - utc_naive(data.start_at)).total_seconds() / 60)
    if minutes <= 0 or minutes > 1440: raise HTTPException(422, "A task block must be longer than zero and no more than 24 hours")
    task_data = TaskIn(title=data.title, goal_id=data.goal_id, module_id=data.module_id,
                       week_start=data.week_start, estimate_minutes=minutes)
    validate_task(db, task_data)
    task = Task(user_id=current_user(db).id, **task_values(task_data))
    db.add(task)
    db.flush()
    start, end = validate_block(db, BlockIn(task_id=task.id, start_at=data.start_at, end_at=data.end_at))
    block = CalendarBlock(task_id=task.id, start_at=start, end_at=end)
    db.add(block)
    db.commit()
    db.refresh(task)
    db.refresh(block)
    return {"task": encoded(task), "block": encoded(block)}

@router.put("/calendar-blocks/{id}")
def edit_block(id: str, data: BlockIn, db: Session = Depends(session)):
    block = owner_block(db, id)
    if block.task_id != data.task_id and db.scalar(select(CompletionLog.id).where(CompletionLog.calendar_block_id == id).limit(1)):
        raise HTTPException(409, "Completed block cannot move to another task")
    start, end = validate_block(db, data, id)
    changed = (block.task_id, block.start_at, block.end_at) != (data.task_id, start, end)
    if changed and block.sync_state == "imported":
        raise HTTPException(409, "Edit the original Google event in Google Calendar; this block is linked for tracking")
    block.task_id, block.start_at, block.end_at = data.task_id, start, end
    if changed and block.google_event_id: block.sync_state = "pending_update"
    return commit(db, block)

@router.post("/calendar-blocks/{id}/result")
def block_result(id: str, data: ResultIn, db: Session = Depends(session)):
    block = owner_block(db, id)
    task = owner_task(db, block.task_id)
    if block.archived_at or task.archived_at: raise HTTPException(422, "Restore the block and task first")
    if data.status == "partial" and not (data.actual_minutes or data.note.strip()):
        raise HTTPException(422, "Partial work needs actual minutes or a note")
    block.status = data.status
    for direct in db.scalars(select(CompletionLog).where(CompletionLog.task_id == task.id, CompletionLog.calendar_block_id.is_(None), CompletionLog.focus_session_id.is_(None))):
        db.delete(direct)
    minutes = data.actual_minutes if data.actual_minutes is not None else round((block.end_at - block.start_at).total_seconds() / 60) if data.status == "done" and not has_recorded_focus(db, task.id) else 0
    replace_log(db, task.id, id, data.status, minutes, data.note)
    db.flush()
    task.status = block_task_status(db, task)
    db.commit()
    return {"block": encoded(block), "task": encoded(task), "totals": completion_totals(db, task.user_id, task.week_start)}

@router.post("/calendar-blocks/review")
def review_blocks(data: ReviewIn, db: Session = Depends(session)):
    ids = [item.block_id for item in data.items]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, "Review each block once")
    selected = [(owner_block(db, item.block_id), item.status) for item in data.items]
    if any(block.archived_at or owner_task(db, block.task_id).archived_at for block, _ in selected):
        raise HTTPException(422, "Restore archived work before reviewing")
    touched = set()
    for block, status in selected:
        block.status = status
        task = owner_task(db, block.task_id)
        touched.add(task.id)
        for direct in db.scalars(select(CompletionLog).where(CompletionLog.task_id == task.id, CompletionLog.calendar_block_id.is_(None), CompletionLog.focus_session_id.is_(None))):
            db.delete(direct)
        minutes = round((block.end_at - block.start_at).total_seconds() / 60) if status == "done" and not has_recorded_focus(db, task.id) else 0
        replace_log(db, task.id, block.id, status, minutes, "")
    db.flush()
    for task_id in touched:
        task = owner_task(db, task_id)
        task.status = block_task_status(db, task)
    db.commit()
    return {"reviewed": len(selected)}

@router.post("/calendar-blocks/{id}/archive")
def archive_block(id: str, restore: bool = False, db: Session = Depends(session)):
    block = owner_block(db, id)
    if block.google_event_id: raise HTTPException(409, "Remove the Google event first from the block editor")
    block.archived_at = None if restore else datetime.now(timezone.utc)
    return commit(db, block)

@router.delete("/calendar-blocks/{id}")
def delete_block(id: str, confirm: bool = Query(False), db: Session = Depends(session)):
    if not confirm: raise HTTPException(400, "Deletion requires confirmation")
    block = owner_block(db, id)
    if block.google_event_id: raise HTTPException(409, "Remove the Google event first from the block editor")
    if db.scalar(select(CompletionLog.id).where(CompletionLog.calendar_block_id == id).limit(1)):
        raise HTTPException(409, "Block has completion history. Archive it instead.")
    db.delete(block)
    db.commit()
    return {"deleted": True}
