"""Personal focus timer. Server timestamps and explicit recording are authoritative."""
from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from db import SessionLocal
from models import CompletionLog, FocusPreferences, FocusSession, Task, User
from plan_api import current_user, encoded

router = APIRouter(prefix="/api/focus")
WORK = ("focus", "starter", "untimed")
TIMED = ("focus", "starter", "short_break", "long_break", "pause", "screen_break")


def session():
    with SessionLocal() as db:
        yield db


def lock(db: Session):
    if db.get_bind().dialect.name == "sqlite":
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    else:
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext('aniro_focus'))"))


def utc(value: datetime | None):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def active(db: Session, user_id: str):
    return db.scalar(select(FocusSession).where(FocusSession.user_id == user_id, FocusSession.ended_at.is_(None)))


def preferences(db: Session, user_id: str):
    value = db.get(FocusPreferences, user_id)
    if not value:
        value = FocusPreferences(user_id=user_id)
        db.add(value)
        db.flush()
    return value


def remaining(item: FocusSession, at: datetime):
    if not item.running or item.phase == "untimed" or not item.ends_at:
        return item.remaining_seconds
    return max(0, min(item.remaining_seconds, int((utc(item.ends_at) - at).total_seconds())))


def elapsed_credit(item: FocusSession, at: datetime):
    if not item.running or item.phase not in WORK or not item.phase_started_at:
        return 0
    elapsed = max(0, (at - utc(item.phase_started_at)).total_seconds())
    return int(min(elapsed, item.remaining_seconds)) if item.phase != "untimed" else int(elapsed)


def stop_clock(item: FocusSession, at: datetime):
    if item.running and item.ends_at:
        item.gap_seconds = max(item.gap_seconds, max(0, int((at - utc(item.ends_at)).total_seconds())))
    elif item.running and item.phase == "untimed" and item.phase_started_at:
        elapsed = int((at - utc(item.phase_started_at)).total_seconds())
        if elapsed > 4 * 3600:
            item.gap_seconds = max(item.gap_seconds, elapsed)
    left = remaining(item, at)
    item.accrued_seconds += elapsed_credit(item, at)
    item.remaining_seconds = left
    item.running = False
    item.phase_started_at = None
    item.ends_at = None


def start_clock(item: FocusSession, phase: str, seconds: int, at: datetime):
    item.phase = phase
    item.remaining_seconds = seconds
    item.running = True
    item.phase_started_at = at
    item.ends_at = at + timedelta(seconds=seconds) if phase != "untimed" else None


def payload(db: Session, item: FocusSession | None, pref: FocusPreferences, at: datetime):
    row = encoded(item) if item else None
    if row:
        row["remaining_seconds_now"] = remaining(item, at)
        row["recordable_minutes"] = max(0, round((item.accrued_seconds + elapsed_credit(item, at)) / 60))
        row["task"] = encoded(db.get(Task, item.task_id)) if item.task_id and db.get(Task, item.task_id) else None
        row["late_seconds"] = max(item.gap_seconds, max(0, int((at - utc(item.ends_at)).total_seconds())) if item.running and item.ends_at and at > utc(item.ends_at) else 0)
    return {"session": row, "preferences": encoded(pref), "server_now": at.isoformat()}


def checked(db: Session, user_id: str, version: int):
    item = active(db, user_id)
    if not item:
        raise HTTPException(404, "No active session")
    if item.version != version:
        raise HTTPException(409, "This session changed in another tab. Refresh to continue.")
    return item


class PreferencesIn(BaseModel):
    focus_minutes: int = Field(ge=1, le=180)
    short_break_minutes: int = Field(ge=1, le=60)
    long_break_minutes: int = Field(ge=1, le=120)
    long_break_every: int = Field(ge=2, le=12)
    sound: bool = False
    auto_transitions: bool = False


class StartIn(BaseModel):
    task_id: str | None = None
    starter: bool = False
    next_action: str = Field(default="", max_length=500)


class ActionIn(BaseModel):
    version: int
    action: Literal["pause", "resume", "end", "discard", "focus", "untimed", "short_break", "long_break", "one_minute_pause", "screen_break", "resume_two_minutes", "change_task", "end_today", "auto_break"]
    task_id: str | None = None
    next_action: str | None = Field(default=None, max_length=500)
    return_instruction: str = Field(default="", max_length=500)


class UpdateIn(BaseModel):
    version: int
    task_id: str | None = None
    next_action: str | None = Field(default=None, max_length=500)
    return_instruction: str | None = Field(default=None, max_length=500)
    distraction_note: str | None = Field(default=None, max_length=1000)


class RecordIn(BaseModel):
    version: int
    recorded_minutes: int = Field(ge=0, le=1440)
    status: Literal["working", "partial", "done"] = "working"
    note: str = Field(default="", max_length=2000)
    next_action: str = Field(default="", max_length=500)
    learning_checked: bool = False
    difficulty: bool = False


class CorrectIn(BaseModel):
    task_id: str | None = None
    recorded_minutes: int = Field(ge=0, le=1440)
    status: Literal["working", "partial", "done"]
    note: str = Field(default="", max_length=2000)
    next_action: str = Field(default="", max_length=500)
    learning_checked: bool = False
    difficulty: bool = False


@router.get("")
def get_focus(db: Session = Depends(session)):
    user = current_user(db)
    pref = db.get(FocusPreferences, user.id) or FocusPreferences(user_id=user.id, focus_minutes=25,
        short_break_minutes=5, long_break_minutes=15, long_break_every=4, sound=False, auto_transitions=False)
    return payload(db, active(db, user.id), pref, datetime.now(timezone.utc))


@router.put("/preferences")
def save_preferences(data: PreferencesIn, db: Session = Depends(session)):
    lock(db)
    user = current_user(db)
    value = preferences(db, user.id)
    for key, val in data.model_dump().items():
        setattr(value, key, val)
    db.commit()
    return encoded(value)


@router.get("/tasks")
def task_choices(db: Session = Depends(session)):
    user = current_user(db)
    return [encoded(t) for t in db.scalars(select(Task).where(Task.user_id == user.id, Task.archived_at.is_(None), Task.status != "done").order_by(Task.week_start.desc(), Task.sort_order, Task.title).limit(100))]


@router.post("/start")
def start(data: StartIn, db: Session = Depends(session)):
    lock(db)
    user = current_user(db)
    if active(db, user.id):
        raise HTTPException(409, "A session is already active")
    if data.task_id:
        task = db.get(Task, data.task_id)
        if not task or task.user_id != user.id or task.archived_at:
            raise HTTPException(422, "Choose an available task")
    pref = preferences(db, user.id)
    at = datetime.now(timezone.utc)
    previous = db.scalar(select(FocusSession).where(FocusSession.user_id == user.id,
                         FocusSession.task_id == data.task_id, FocusSession.ended_at.is_not(None))
                         .order_by(FocusSession.ended_at.desc()).limit(1)) if data.task_id else None
    item = FocusSession(user_id=user.id, task_id=data.task_id, next_action=data.next_action.strip() or (previous.next_action if previous and previous.next_action else task.title if data.task_id else ""), started_at=at)
    start_clock(item, "starter" if data.starter else "focus", 120 if data.starter else pref.focus_minutes * 60, at)
    db.add(item)
    db.commit()
    return payload(db, item, pref, at)


@router.post("/action")
def action(data: ActionIn, db: Session = Depends(session)):
    lock(db)
    user = current_user(db)
    item = checked(db, user.id, data.version)
    pref = preferences(db, user.id)
    at = datetime.now(timezone.utc)
    previous_phase = item.phase
    if data.next_action is not None:
        item.next_action = data.next_action.strip()
    complete = item.running and item.phase in TIMED and remaining(item, at) == 0
    if data.action == "pause":
        if not item.running or item.phase not in WORK:
            raise HTTPException(422, "This timer cannot be paused now")
        stop_clock(item, at)
    elif data.action == "resume":
        if item.phase in ("pause", "screen_break"):
            if item.running:
                stop_clock(item, at)
            start_clock(item, item.return_phase, item.return_seconds, at)
        elif not item.running and item.phase in WORK:
            start_clock(item, item.phase, item.remaining_seconds, at)
        else:
            raise HTTPException(422, "There is no paused work to resume")
    elif data.action in ("end", "end_today"):
        if item.running:
            stop_clock(item, at)
        item.phase = "summary"
        item.remaining_seconds = 0
    elif data.action == "discard":
        if item.running:
            stop_clock(item, at)
        item.phase = "unrecorded"
        item.ended_at = at
    elif data.action == "change_task":
        if item.running:
            stop_clock(item, at)
        if data.task_id:
            task = db.get(Task, data.task_id)
            if not task or task.user_id != user.id or task.archived_at:
                raise HTTPException(422, "Choose an available task")
        item.task_id = data.task_id
        item.next_action = db.get(Task, data.task_id).title if data.task_id else ""
        item.phase = "return"
    elif data.action in ("short_break", "long_break", "auto_break"):
        if item.running:
            stop_clock(item, at)
        if previous_phase == "focus" and complete:
            item.focus_intervals += 1
        if data.return_instruction.strip():
            item.return_instruction = data.return_instruction.strip()
        elif not item.return_instruction:
            item.return_instruction = item.next_action
        kind = data.action
        if kind == "auto_break":
            kind = "long_break" if item.focus_intervals and item.focus_intervals % pref.long_break_every == 0 else "short_break"
        start_clock(item, kind, (pref.long_break_minutes if kind == "long_break" else pref.short_break_minutes) * 60, at)
    elif data.action in ("one_minute_pause", "screen_break"):
        item.return_phase = item.phase if item.phase in WORK else "focus"
        if item.running:
            stop_clock(item, at)
        item.return_seconds = item.remaining_seconds if item.return_phase != "untimed" else 0
        start_clock(item, "pause" if data.action == "one_minute_pause" else "screen_break", 60, at)
    elif data.action in ("focus", "resume_two_minutes", "untimed"):
        if item.running:
            stop_clock(item, at)
        if previous_phase == "focus" and complete:
            item.focus_intervals += 1
        seconds = 120 if data.action == "resume_two_minutes" else pref.focus_minutes * 60
        start_clock(item, "starter" if data.action == "resume_two_minutes" else data.action, seconds, at)
    else:
        raise HTTPException(422, "Unknown action")
    item.version += 1
    db.commit()
    return payload(db, item, pref, at)


@router.patch("")
def update_session(data: UpdateIn, db: Session = Depends(session)):
    lock(db)
    user = current_user(db)
    item = checked(db, user.id, data.version)
    if data.task_id is not None:
        task = db.get(Task, data.task_id)
        if not task or task.user_id != user.id or task.archived_at:
            raise HTTPException(422, "Choose an available task")
        item.task_id = data.task_id
    for field in ("next_action", "return_instruction", "distraction_note"):
        value = getattr(data, field)
        if value is not None:
            setattr(item, field, value.strip())
    item.version += 1
    db.commit()
    return payload(db, item, preferences(db, user.id), datetime.now(timezone.utc))


def set_result(db: Session, item: FocusSession, data: RecordIn | CorrectIn):
    item.next_action = data.next_action.strip()
    item.learning_checked = data.learning_checked
    item.difficulty = data.difficulty
    item.recorded_minutes = data.recorded_minutes
    item.result_status = data.status
    item.result_note = data.note.strip()
    if not item.task_id:
        return
    task = db.get(Task, item.task_id)
    log = db.scalar(select(CompletionLog).where(CompletionLog.focus_session_id == item.id))
    if not log:
        log = CompletionLog(task_id=task.id, focus_session_id=item.id)
        db.add(log)
    log.completed_minutes = data.recorded_minutes
    log.result = data.status
    log.note = data.note.strip()
    if data.status == "done":
        task.status = "done"
    elif data.status == "partial" and task.status != "done":
        task.status = "partial"


@router.post("/record")
def record(data: RecordIn, db: Session = Depends(session)):
    lock(db)
    user = current_user(db)
    item = checked(db, user.id, data.version)
    at = datetime.now(timezone.utc)
    if item.running:
        stop_clock(item, at)
    item.phase = "summary"
    set_result(db, item, data)
    item.ended_at = at
    item.version += 1
    db.commit()
    return {"session": encoded(item), "recorded_minutes": data.recorded_minutes}


@router.get("/history")
def history(db: Session = Depends(session)):
    user = current_user(db)
    rows = list(db.scalars(select(FocusSession).where(FocusSession.user_id == user.id, FocusSession.ended_at.is_not(None)).order_by(FocusSession.ended_at.desc()).limit(30)))
    return [{**encoded(item), "task_title": db.get(Task, item.task_id).title if item.task_id and db.get(Task, item.task_id) else None,
             "log": encoded(log) if (log := db.scalar(select(CompletionLog).where(CompletionLog.focus_session_id == item.id))) else ({"completed_minutes": item.recorded_minutes, "result": item.result_status, "note": item.result_note} if item.recorded_minutes is not None else None)} for item in rows]


@router.put("/history/{id}")
def correct(id: str, data: CorrectIn, db: Session = Depends(session)):
    lock(db)
    user = current_user(db)
    item = db.get(FocusSession, id)
    if not item or item.user_id != user.id or not item.ended_at:
        raise HTTPException(404, "Recorded session not found")
    if item.recorded_minutes is None:
        raise HTTPException(422, "This session was not recorded")
    if data.task_id and not item.task_id:
        task = db.get(Task, data.task_id)
        if not task or task.user_id != user.id or task.archived_at:
            raise HTTPException(422, "Choose an available task")
        item.task_id = task.id
    elif data.task_id and data.task_id != item.task_id:
        raise HTTPException(422, "Correct this attempt on its original task")
    previous = item.result_status
    set_result(db, item, data)
    if item.task_id and previous in ("done", "partial") and data.status != previous:
        task = db.get(Task, item.task_id)
        other = list(db.scalars(select(CompletionLog).where(CompletionLog.task_id == item.task_id, CompletionLog.focus_session_id != item.id)))
        task.status = "done" if any(log.result == "done" for log in other) else "partial" if data.status == "partial" or any(log.result == "partial" for log in other) else "planned"
    db.commit()
    return {"session": encoded(item)}
