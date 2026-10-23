"""Stage 3 local reflection, money, and portable exports."""
import csv
import io
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete, insert, update, DateTime
from sqlalchemy.orm import Session
from db import SessionLocal
from models import (User, LifeArea, Track, Module, Vision, Goal, WeeklyPlan, Task, CalendarBlock,
                    CompletionLog, Habit, HabitCheckin, BalanceTarget, AreaBalanceTarget, ReflectSettings,
                    BudgetMonth, ExpenseCategory, Expense, GoogleIntegration, CoachUsage, BackupSnapshot)

router = APIRouter(prefix="/api")

def session():
    with SessionLocal() as db:
        yield db

def user(db: Session):
    value = db.scalar(select(User).limit(1))
    if value is None:
        value = User()
        db.add(value)
        db.commit()
        db.refresh(value)
    return value

def get(db: Session, cls, id: str):
    value = db.get(cls, id)
    if value is None:
        raise HTTPException(404, "Record not found")
    return value

def owned(db: Session, cls, id: str):
    value = get(db, cls, id)
    if value.user_id != user(db).id:
        raise HTTPException(404, "Record not found")
    return value

def dump(item):
    result = {}
    for column in item.__table__.columns:
        value = getattr(item, column.name)
        if isinstance(value, datetime):
            value = (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value).isoformat()
        result[column.name] = value
    return result

def save(db: Session, value):
    db.add(value)
    db.commit()
    db.refresh(value)
    return dump(value)

def day(value: str):
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(422, "Use a valid YYYY-MM-DD date")

def week_start(value: str):
    parsed = day(value)
    if parsed.weekday() != 0:
        raise HTTPException(422, "Week must start on Monday")
    return parsed

def month_key(value: str):
    try:
        parsed = date.fromisoformat(value + "-01")
    except ValueError:
        raise HTTPException(422, "Use a valid YYYY-MM month")
    if parsed.strftime("%Y-%m") != value:
        raise HTTPException(422, "Use a valid YYYY-MM month")
    return parsed

def local_today(db: Session):
    return datetime.now(ZoneInfo(user(db).timezone)).date()

class HabitIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    life_area_id: str
    track_id: str | None = None
    frequency_rule: str = Field(default="daily", pattern="^(daily|weekdays)$")

class TargetIn(BaseModel):
    target_minutes: int = Field(ge=0, le=10080)

class ReflectSettingsIn(BaseModel):
    coach_trigger_count: int = Field(ge=2, le=10)

class BudgetIn(BaseModel):
    limit_minor: int = Field(ge=0, le=1_000_000_000)

class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    color_key: str = Field(default="lime", max_length=30)

class ExpenseIn(BaseModel):
    category_id: str
    amount_minor: int = Field(gt=0, le=1_000_000_000)
    spent_on: str
    description: str = Field(default="", max_length=240)

class QuickExpenseIn(BaseModel):
    category_name: str = Field(min_length=1, max_length=120)
    amount_minor: int = Field(gt=0, le=1_000_000_000)
    spent_on: str
    description: str = Field(default="", max_length=240)

def validate_habit_links(db: Session, value: HabitIn):
    area = owned(db, LifeArea, value.life_area_id)
    if area.archived_at:
        raise HTTPException(422, "Restore the life area first")
    track = owned_track(db, value.track_id) if value.track_id else None
    if track and (track.life_area_id != area.id or track.archived_at):
        raise HTTPException(422, "Track does not belong to the active life area")
    return track.color_key if track else area.color_key

def owned_track(db: Session, id: str):
    track = get(db, Track, id)
    owned(db, LifeArea, track.life_area_id)
    return track

@router.get("/habits")
def habits(db: Session = Depends(session)):
    u = user(db)
    return [dump(h) for h in db.scalars(select(Habit).where(Habit.user_id == u.id).order_by(Habit.name))]

@router.post("/habits", status_code=201)
def add_habit(data: HabitIn, db: Session = Depends(session)):
    color = validate_habit_links(db, data)
    return save(db, Habit(user_id=user(db).id, created_on=local_today(db).isoformat(),
                          color_key=color, **data.model_dump()))

@router.put("/habits/{id}")
def edit_habit(id: str, data: HabitIn, db: Session = Depends(session)):
    habit = owned(db, Habit, id)
    color = validate_habit_links(db, data)
    for key, value in data.model_dump().items():
        setattr(habit, key, value)
    habit.color_key = color
    return save(db, habit)

@router.post("/habits/{id}/archive")
def archive_habit(id: str, restore: bool = False, db: Session = Depends(session)):
    habit = owned(db, Habit, id)
    habit.archived_at = None if restore else datetime.now(timezone.utc)
    return save(db, habit)

@router.delete("/habits/{id}")
def delete_habit(id: str, confirm: bool = Query(False), db: Session = Depends(session)):
    if not confirm:
        raise HTTPException(400, "Deletion requires confirmation")
    habit = owned(db, Habit, id)
    if db.scalar(select(HabitCheckin.id).where(HabitCheckin.habit_id == id).limit(1)):
        raise HTTPException(409, "Habit has check-ins. Archive it instead.")
    db.delete(habit)
    db.commit()
    return {"deleted": True}

@router.put("/habits/{id}/checkins/{local_date}")
def check_habit(id: str, local_date: str, db: Session = Depends(session)):
    habit = owned(db, Habit, id)
    if habit.archived_at:
        raise HTTPException(422, "Restore the habit first")
    value = day(local_date)
    if value > local_today(db):
        raise HTTPException(422, "Cannot check in for a future day")
    if value < day(habit.created_on):
        raise HTTPException(422, "Day is before habit creation")
    checkin = db.scalar(select(HabitCheckin).where(HabitCheckin.habit_id == id, HabitCheckin.local_date == local_date))
    return save(db, checkin or HabitCheckin(habit_id=id, local_date=local_date, status="done"))

@router.delete("/habits/{id}/checkins/{local_date}")
def uncheck_habit(id: str, local_date: str, db: Session = Depends(session)):
    owned(db, Habit, id)
    checkin = db.scalar(select(HabitCheckin).where(HabitCheckin.habit_id == id, HabitCheckin.local_date == local_date))
    if checkin:
        db.delete(checkin)
        db.commit()
    return {"deleted": bool(checkin)}

@router.put("/reflect/targets/{track_id}")
def set_target(track_id: str, data: TargetIn, db: Session = Depends(session)):
    owned_track(db, track_id)
    u = user(db)
    target = db.scalar(select(BalanceTarget).where(BalanceTarget.user_id == u.id, BalanceTarget.track_id == track_id))
    if target is None:
        target = BalanceTarget(user_id=u.id, track_id=track_id, target_minutes=data.target_minutes)
    target.target_minutes = data.target_minutes
    return save(db, target)

@router.put("/reflect/area-targets/{area_id}")
def set_area_target(area_id: str, data: TargetIn, db: Session = Depends(session)):
    owned(db, LifeArea, area_id)
    u = user(db)
    target = db.scalar(select(AreaBalanceTarget).where(AreaBalanceTarget.user_id == u.id, AreaBalanceTarget.life_area_id == area_id))
    if target is None:
        target = AreaBalanceTarget(user_id=u.id, life_area_id=area_id, target_minutes=data.target_minutes)
    target.target_minutes = data.target_minutes
    return save(db, target)

@router.put("/reflect/settings")
def set_reflect_settings(data: ReflectSettingsIn, db: Session = Depends(session)):
    u = user(db)
    settings = db.get(ReflectSettings, u.id) or ReflectSettings(user_id=u.id)
    settings.coach_trigger_count = data.coach_trigger_count
    return save(db, settings)

def streak_stats(habit: Habit, checked: set[str], today: date):
    start = max(day(habit.created_on), today - timedelta(days=29))
    relevant = [today - timedelta(days=n) for n in range(29, -1, -1)
                if today - timedelta(days=n) >= start and (habit.frequency_rule != "weekdays" or (today - timedelta(days=n)).weekday() < 5)]
    checked_count = sum(d.isoformat() in checked for d in relevant)
    rate = round(100 * checked_count / len(relevant)) if relevant else 0
    cursor = today
    if habit.frequency_rule == "weekdays":
        while cursor.weekday() >= 5:
            cursor -= timedelta(days=1)
    if cursor.isoformat() not in checked:
        cursor -= timedelta(days=1)
    streak = 0
    while cursor >= day(habit.created_on):
        if habit.frequency_rule == "weekdays" and cursor.weekday() >= 5:
            cursor -= timedelta(days=1)
            continue
        if cursor.isoformat() not in checked:
            break
        streak += 1
        cursor -= timedelta(days=1)
    return {"consistency_pct": rate, "consistency_checked": checked_count,
            "consistency_eligible": len(relevant), "current_streak": streak}

def reflect_summary(db: Session, week: str, today_override: date | None = None):
    start = week_start(week)
    u = user(db)
    today = today_override or local_today(db)
    areas = list(db.scalars(select(LifeArea).where(LifeArea.user_id == u.id)))
    tracks = list(db.scalars(select(Track).join(LifeArea).where(LifeArea.user_id == u.id)))
    modules = list(db.scalars(select(Module).join(Track).join(LifeArea).where(LifeArea.user_id == u.id)))
    area_map = {a.id: a for a in areas}
    track_map = {t.id: t for t in tracks}
    module_map = {m.id: m for m in modules}
    goals = {g.id: g for g in db.scalars(select(Goal).where(Goal.user_id == u.id, Goal.target_date == week))}
    visions = {v.id: v for v in db.scalars(select(Vision).where(Vision.user_id == u.id))}
    tasks = list(db.scalars(select(Task).where(Task.user_id == u.id, Task.week_start == week)))
    task_map = {t.id: t for t in tasks}
    blocks = list(db.scalars(select(CalendarBlock).where(CalendarBlock.task_id.in_(task_map)))) if tasks else []
    logs = list(db.scalars(select(CompletionLog).where(CompletionLog.task_id.in_(task_map)))) if tasks else []
    blocks_by_id = {b.id: b for b in blocks}
    totals = {}
    def group(task: Task):
        goal = goals.get(task.goal_id)
        module = module_map.get(task.module_id or (goal.module_id if goal else None))
        track = track_map.get(module.track_id if module else goal.track_id if goal else None)
        area = area_map.get(track.life_area_id if track else goal.life_area_id if goal else None)
        return area, track, module
    def record(task: Task):
        area, track, module = group(task)
        key = (area.id if area else None, track.id if track else None, module.id if module else None)
        if key not in totals:
            totals[key] = {"area_id": key[0], "area_name": area.name if area else "Unassigned",
                           "track_id": key[1], "track_name": track.name if track else "No track",
                           "module_id": key[2], "module_name": module.name if module else "No module",
                           "color_key": track.color_key if track else area.color_key if area else "lime",
                           "planned_minutes": 0, "completed_minutes": 0, "completed_tasks": 0,
                           "last_activity_date": None, "shortfalls": 0,
                           "suggested_task_id": None, "suggested_block_id": None}
        return totals[key]
    for task in tasks:
        row = record(task)
        if task.status == "done":
            row["completed_tasks"] += 1
    for block in blocks:
        if block.archived_at is None:
            row = record(task_map[block.task_id])
            row["planned_minutes"] += round((block.end_at - block.start_at).total_seconds() / 60)
            if block.status in ("partial", "missed"):
                row["shortfalls"] += 1
                row["suggested_task_id"] = block.task_id
                row["suggested_block_id"] = block.id
    for log in logs:
        row = record(task_map[log.task_id])
        row["completed_minutes"] += log.completed_minutes
        activity = (blocks_by_id[log.calendar_block_id].start_at if log.calendar_block_id in blocks_by_id else log.recorded_at)
        activity_date = activity.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(u.timezone)).date().isoformat()
        if row["last_activity_date"] is None or activity_date > row["last_activity_date"]:
            row["last_activity_date"] = activity_date
    goal_rows = {}
    for goal in goals.values():
        area = area_map.get(goal.life_area_id)
        vision = visions.get(goal.parent_vision_id)
        goal_rows[goal.id] = {"id": goal.id, "title": goal.title, "status": goal.status,
                              "archived": goal.archived_at is not None,
                              "area_id": goal.life_area_id, "area_name": area.name if area else "Area",
                              "color_key": area.color_key if area else "lime",
                              "vision_id": vision.id if vision else None,
                              "vision_title": vision.title if vision else None,
                              "task_count": 0, "completed_tasks": 0,
                              "planned_minutes": 0, "completed_minutes": 0,
                              "sort_order": goal.sort_order}
    for task in tasks:
        row = goal_rows.get(task.goal_id)
        if row:
            row["task_count"] += 1
            row["completed_tasks"] += task.status == "done"
    for block in blocks:
        row = goal_rows.get(task_map[block.task_id].goal_id)
        if row and block.archived_at is None:
            row["planned_minutes"] += round((block.end_at - block.start_at).total_seconds() / 60)
    for log in logs:
        row = goal_rows.get(task_map[log.task_id].goal_id)
        if row:
            row["completed_minutes"] += log.completed_minutes
    settings = db.get(ReflectSettings, u.id)
    trigger = settings.coach_trigger_count if settings else 2
    prompts = []
    for row in totals.values():
        if row["shortfalls"] >= trigger and row["planned_minutes"] > row["completed_minutes"]:
            label = " → ".join(x for x in (row["track_name"] if row["track_id"] else row["area_name"], row["module_name"] if row["module_id"] else None) if x)
            prompts.append({"text": f"You planned {row['planned_minutes']} minutes for {label} and recorded {row['completed_minutes']} minutes across {row['shortfalls']} partial or missed blocks. What changed in the plan?", "actions": ["Reschedule", "Reduce", "Reprioritize", "Archive"], "track_id": row["track_id"], "task_id": row["suggested_task_id"], "block_id": row["suggested_block_id"]})
    habits = list(db.scalars(select(Habit).where(Habit.user_id == u.id).order_by(Habit.name)))
    all_checks = list(db.scalars(select(HabitCheckin).where(HabitCheckin.habit_id.in_([h.id for h in habits])))) if habits else []
    checks_by_habit = {}
    for check in all_checks:
        checks_by_habit.setdefault(check.habit_id, set()).add(check.local_date)
    habit_rows = [{**dump(h), "area_name": area_map[h.life_area_id].name if h.life_area_id in area_map else "Area",
                   "track_name": track_map[h.track_id].name if h.track_id in track_map else None,
                   "checked_dates": sorted(checks_by_habit.get(h.id, set())),
                   **streak_stats(h, checks_by_habit.get(h.id, set()), today)} for h in habits]
    targets = {t.track_id: t.target_minutes for t in db.scalars(select(BalanceTarget).where(BalanceTarget.user_id == u.id))}
    area_targets = {t.life_area_id: t.target_minutes for t in db.scalars(select(AreaBalanceTarget).where(AreaBalanceTarget.user_id == u.id))}
    group_rows = list(totals.values())
    balance_rows = []
    for area in areas:
        rows = [r for r in group_rows if r["area_id"] == area.id]
        balance_rows.append({"id": area.id, "scope": "area", "name": area.name, "area_name": area.name,
                             "color_key": area.color_key, "target_minutes": area_targets.get(area.id),
                             "planned_minutes": sum(r["planned_minutes"] for r in rows),
                             "completed_minutes": sum(r["completed_minutes"] for r in rows)})
    for track in tracks:
        rows = [r for r in group_rows if r["track_id"] == track.id]
        balance_rows.append({"id": track.id, "scope": "track", "name": track.name, "area_name": area_map[track.life_area_id].name,
                           "color_key": track.color_key, "target_minutes": targets.get(track.id),
                           "planned_minutes": sum(r["planned_minutes"] for r in rows),
                           "completed_minutes": sum(r["completed_minutes"] for r in rows)})
    return {"week": week, "today": today.isoformat(), "timezone": u.timezone, "areas": [dump(a) for a in areas],
            "tracks": [dump(t) for t in tracks], "habits": habit_rows,
            "goals": sorted(goal_rows.values(), key=lambda r: (r["sort_order"], r["title"])),
            "modules": sorted(group_rows, key=lambda r: (r["area_name"], r["track_name"], r["module_name"])),
            "balance": balance_rows, "prompts": prompts, "coach_trigger_count": trigger,
            "totals": {"planned_minutes": sum(r["planned_minutes"] for r in group_rows),
                       "completed_minutes": sum(r["completed_minutes"] for r in group_rows),
                       "completed_tasks": sum(r["completed_tasks"] for r in group_rows)}}

@router.get("/reflect")
def reflect(week: str, db: Session = Depends(session)):
    return reflect_summary(db, week)

def budget_for(db: Session, year: int, month: int):
    return db.scalar(select(BudgetMonth).where(BudgetMonth.user_id == user(db).id,
                                                BudgetMonth.year == year, BudgetMonth.month == month))

def money_summary(db: Session, month: str, today_override: date | None = None):
    parsed = month_key(month)
    u = user(db)
    budget = budget_for(db, parsed.year, parsed.month)
    categories = list(db.scalars(select(ExpenseCategory).where(ExpenseCategory.user_id == u.id).order_by(ExpenseCategory.name)))
    category_map = {c.id: c for c in categories}
    expenses = list(db.scalars(select(Expense).where(Expense.budget_month_id == budget.id).order_by(Expense.spent_on.desc(), Expense.id.desc()))) if budget else []
    spent = sum(e.amount_minor for e in expenses)
    remaining = budget.limit_minor - spent if budget else None
    today = today_override or local_today(db)
    if today.strftime("%Y-%m") == month and remaining is not None:
        next_month = (parsed.replace(day=28) + timedelta(days=4)).replace(day=1)
        days_remaining = (next_month - today).days
        daily_allowance = remaining // days_remaining if days_remaining else None
    else:
        daily_allowance = None
    breakdown = []
    for category in categories:
        total = sum(e.amount_minor for e in expenses if e.category_id == category.id)
        if total:
            breakdown.append({"category_id": category.id, "name": category.name,
                              "color_key": category.color_key, "amount_minor": total,
                              "percentage": round(total * 100 / spent, 1) if spent else 0})
    return {"month": month, "today": today.isoformat(), "timezone": u.timezone, "currency": "LKR", "budget": dump(budget) if budget else None,
            "categories": [dump(c) for c in categories],
            "expenses": [{**dump(e), "category_name": category_map[e.category_id].name,
                          "category_color": category_map[e.category_id].color_key} for e in expenses],
            "spent_minor": spent, "remaining_minor": remaining, "over_budget": remaining is not None and remaining < 0,
            "daily_allowance_minor": daily_allowance, "breakdown": breakdown}

@router.get("/money")
def money(month: str, db: Session = Depends(session)):
    return money_summary(db, month)

@router.put("/budgets/{month}")
def set_budget(month: str, data: BudgetIn, db: Session = Depends(session)):
    parsed = month_key(month)
    budget = budget_for(db, parsed.year, parsed.month)
    if budget is None:
        budget = BudgetMonth(user_id=user(db).id, year=parsed.year, month=parsed.month,
                             currency="LKR", limit_minor=data.limit_minor)
    budget.limit_minor = data.limit_minor
    return save(db, budget)

@router.post("/expense-categories", status_code=201)
def add_category(data: CategoryIn, db: Session = Depends(session)):
    return save(db, ExpenseCategory(user_id=user(db).id, **data.model_dump()))

@router.put("/expense-categories/{id}")
def edit_category(id: str, data: CategoryIn, db: Session = Depends(session)):
    category = owned(db, ExpenseCategory, id)
    for key, value in data.model_dump().items():
        setattr(category, key, value)
    return save(db, category)

@router.post("/expense-categories/{id}/archive")
def archive_category(id: str, restore: bool = False, db: Session = Depends(session)):
    category = owned(db, ExpenseCategory, id)
    category.archived_at = None if restore else datetime.now(timezone.utc)
    return save(db, category)

@router.delete("/expense-categories/{id}")
def delete_category(id: str, confirm: bool = Query(False), db: Session = Depends(session)):
    if not confirm:
        raise HTTPException(400, "Deletion requires confirmation")
    category = owned(db, ExpenseCategory, id)
    if db.scalar(select(Expense.id).where(Expense.category_id == id).limit(1)):
        raise HTTPException(409, "Category has expenses. Archive it instead.")
    db.delete(category)
    db.commit()
    return {"deleted": True}

def validate_expense(db: Session, data: ExpenseIn):
    spent_on = day(data.spent_on)
    category = owned(db, ExpenseCategory, data.category_id)
    if category.archived_at:
        raise HTTPException(422, "Restore the category first")
    return spent_on

@router.post("/expenses", status_code=201)
def add_expense(data: ExpenseIn, db: Session = Depends(session)):
    spent_on = validate_expense(db, data)
    budget = budget_for(db, spent_on.year, spent_on.month)
    if budget is None:
        raise HTTPException(422, "Set this month's budget first")
    return save(db, Expense(budget_month_id=budget.id, **data.model_dump()))

@router.post("/expenses/quick", status_code=201)
def add_expense_with_category(data: QuickExpenseIn, db: Session = Depends(session)):
    name = data.category_name.strip()
    if not name:
        raise HTTPException(422, "Enter a category name")
    spent_on = day(data.spent_on)
    budget = budget_for(db, spent_on.year, spent_on.month)
    if budget is None:
        raise HTTPException(422, "Set this month's budget first")
    category = ExpenseCategory(user_id=user(db).id, name=name, color_key="lime")
    db.add(category)
    db.flush()
    expense = Expense(budget_month_id=budget.id, category_id=category.id,
                      amount_minor=data.amount_minor, spent_on=data.spent_on,
                      description=data.description)
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return dump(expense)

@router.put("/expenses/{id}")
def edit_expense(id: str, data: ExpenseIn, db: Session = Depends(session)):
    expense = get(db, Expense, id)
    old_month = get(db, BudgetMonth, expense.budget_month_id)
    if old_month.user_id != user(db).id:
        raise HTTPException(404, "Record not found")
    spent_on = validate_expense(db, data)
    budget = budget_for(db, spent_on.year, spent_on.month)
    if budget is None:
        raise HTTPException(422, "Set the destination month's budget first")
    for key, value in data.model_dump().items():
        setattr(expense, key, value)
    expense.budget_month_id = budget.id
    return save(db, expense)

@router.delete("/expenses/{id}")
def delete_expense(id: str, confirm: bool = Query(False), db: Session = Depends(session)):
    if not confirm:
        raise HTTPException(400, "Deletion requires confirmation")
    expense = get(db, Expense, id)
    if get(db, BudgetMonth, expense.budget_month_id).user_id != user(db).id:
        raise HTTPException(404, "Record not found")
    db.delete(expense)
    db.commit()
    return {"deleted": True}

EXPORT_TABLES = (LifeArea, Track, Module, Vision, Goal, WeeklyPlan, Task, CalendarBlock, CompletionLog,
                 Habit, HabitCheckin, BalanceTarget, AreaBalanceTarget, ReflectSettings, BudgetMonth, ExpenseCategory, Expense)

def validate_backup(payload: dict):
    if payload.get("format") != "aniro-json-v1" or not isinstance(payload.get("user"), dict):
        raise HTTPException(422, "Choose an Aniro JSON backup")
    tables = payload.get("tables")
    if not isinstance(tables, dict) or set(tables) != {cls.__tablename__ for cls in EXPORT_TABLES}:
        raise HTTPException(422, "Backup tables do not match this version of Aniro")
    source_user = payload["user"].get("id")
    if not isinstance(source_user, str) or not source_user:
        raise HTTPException(422, "Backup user is missing")
    total = 0
    for cls in EXPORT_TABLES:
        rows = tables[cls.__tablename__]
        if not isinstance(rows, list) or len(rows) > 100_000:
            raise HTTPException(422, "Backup table is invalid or too large")
        columns = {column.name for column in cls.__table__.columns}
        ids = set()
        for row in rows:
            if not isinstance(row, dict) or set(row) != columns or not isinstance(row.get("id", row.get("user_id")), str):
                raise HTTPException(422, f"Invalid {cls.__tablename__} record")
            if "user_id" in row and row["user_id"] != source_user:
                raise HTTPException(422, "Backup includes records from another user")
            identifier = row.get("id", row.get("user_id"))
            if identifier in ids:
                raise HTTPException(422, f"Duplicate {cls.__tablename__} record")
            ids.add(identifier)
        total += len(rows)
    return total

@router.post("/import/preview")
def preview_backup(payload: dict):
    total = validate_backup(payload)
    return {"records": total, "exported_at": payload.get("exported_at"),
            "tables": {name: len(rows) for name, rows in payload["tables"].items()}}

@router.post("/import/restore")
def restore_backup(payload: dict, confirm: bool = Query(False), db: Session = Depends(session)):
    if not confirm:
        raise HTTPException(400, "Restoring requires confirmation")
    total = validate_backup(payload)
    bind = db.get_bind()
    if bind.dialect.name == "sqlite" and bind.url.database and bind.url.database != ":memory:":
        source = Path(bind.url.database)
        backup_dir = source.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        snapshot = backup_dir / f"aniro-before-restore-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')}.db"
        with closing(sqlite3.connect(source)) as original, closing(sqlite3.connect(snapshot)) as saved:
            original.backup(saved)
        snapshot_name = str(snapshot)
    elif bind.dialect.name == "postgresql":
        snapshot = BackupSnapshot(payload=export_json(db).body.decode("utf-8"))
        db.add(snapshot)
        db.commit()
        snapshot_name = snapshot.id
    else:
        raise HTTPException(501, "Restore requires persistent SQLite or Postgres storage")

    current_user = user(db)
    source_user = payload["user"]["id"]
    try:
        for cls in reversed(EXPORT_TABLES):
            db.execute(delete(cls))
        db.execute(delete(GoogleIntegration))
        db.execute(delete(CoachUsage))
        pending_vision_links = []
        for cls in EXPORT_TABLES:
            for raw in payload["tables"][cls.__tablename__]:
                row = dict(raw)
                if row.get("user_id") == source_user:
                    row["user_id"] = current_user.id
                for column in cls.__table__.columns:
                    if isinstance(column.type, DateTime) and row[column.name] is not None:
                        row[column.name] = datetime.fromisoformat(row[column.name])
                if cls is Vision and row["parent_vision_id"]:
                    pending_vision_links.append((row["id"], row["parent_vision_id"]))
                    row["parent_vision_id"] = None
                db.execute(insert(cls).values(**row))
        for child_id, parent_id in pending_vision_links:
            db.execute(update(Vision).where(Vision.id == child_id).values(parent_vision_id=parent_id))
        imported_user = payload["user"]
        current_user.display_name = imported_user.get("display_name") or current_user.display_name
        current_user.timezone = imported_user.get("timezone") or current_user.timezone
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(422, f"Backup could not be restored: {type(exc).__name__}") from exc
    return {"restored": total, "snapshot": snapshot_name, "local_snapshot": snapshot_name}

@router.get("/import/snapshots")
def backup_snapshots(db: Session = Depends(session)):
    if db.get_bind().dialect.name != "postgresql": return {"snapshots": []}
    rows = db.scalars(select(BackupSnapshot).order_by(BackupSnapshot.created_at.desc()).limit(20))
    return {"snapshots": [{"id": row.id, "created_at": row.created_at.isoformat()} for row in rows]}

@router.get("/import/snapshots/{id}")
def download_snapshot(id: str, db: Session = Depends(session)):
    snapshot = get(db, BackupSnapshot, id)
    return Response(snapshot.payload, media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="aniro-snapshot-{id}.json"'})

@router.get("/export/json")
def export_json(db: Session = Depends(session)):
    u = user(db)
    area_ids = select(LifeArea.id).where(LifeArea.user_id == u.id)
    track_ids = select(Track.id).where(Track.life_area_id.in_(area_ids))
    task_ids = select(Task.id).where(Task.user_id == u.id)
    habit_ids = select(Habit.id).where(Habit.user_id == u.id)
    budget_ids = select(BudgetMonth.id).where(BudgetMonth.user_id == u.id)
    filters = {LifeArea: LifeArea.user_id == u.id, Track: Track.life_area_id.in_(area_ids),
               Module: Module.track_id.in_(track_ids), Vision: Vision.user_id == u.id, Goal: Goal.user_id == u.id,
               WeeklyPlan: WeeklyPlan.user_id == u.id, Task: Task.user_id == u.id,
               CalendarBlock: CalendarBlock.task_id.in_(task_ids), CompletionLog: CompletionLog.task_id.in_(task_ids),
               Habit: Habit.user_id == u.id, HabitCheckin: HabitCheckin.habit_id.in_(habit_ids),
               BalanceTarget: BalanceTarget.user_id == u.id, AreaBalanceTarget: AreaBalanceTarget.user_id == u.id,
               ReflectSettings: ReflectSettings.user_id == u.id,
               BudgetMonth: BudgetMonth.user_id == u.id, ExpenseCategory: ExpenseCategory.user_id == u.id,
               Expense: Expense.budget_month_id.in_(budget_ids)}
    payload = {"format": "aniro-json-v1", "exported_at": datetime.now(timezone.utc).isoformat(),
               "user": dump(u), "tables": {cls.__tablename__: [dump(item) for item in db.scalars(select(cls).where(filters[cls]))]
                                          for cls in EXPORT_TABLES}}
    return Response(json.dumps(payload, ensure_ascii=False, indent=2), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="aniro-backup.json"'})

@router.get("/export/expenses.csv")
def export_expenses_csv(month: str | None = None, db: Session = Depends(session)):
    u = user(db)
    if month:
        month_key(month)
    query = select(Expense, BudgetMonth, ExpenseCategory).join(BudgetMonth).join(ExpenseCategory).where(BudgetMonth.user_id == u.id)
    if month:
        parsed = month_key(month)
        query = query.where(BudgetMonth.year == parsed.year, BudgetMonth.month == parsed.month)
    rows = db.execute(query.order_by(Expense.spent_on, Expense.id)).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "date", "month", "category", "amount_lkr", "description"])
    for expense, budget, category in rows:
        writer.writerow([expense.id, expense.spent_on, f"{budget.year:04d}-{budget.month:02d}",
                         category.name, f"{expense.amount_minor / 100:.2f}", expense.description])
    return Response(output.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="aniro-expenses.csv"'})
