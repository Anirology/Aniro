"""Idempotently fill every demo-safe, user-facing table with realistic data."""
from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func, select

from db import SessionLocal
from models import (
    AreaBalanceTarget, BalanceTarget, BudgetMonth, CalendarBlock, CoachUsage, CompletionLog,
    Expense, ExpenseCategory, ExpenseEnvelope, FinancialAccount, FocusPreferences, FocusSession,
    Goal, Habit, HabitCheckin, LifeArea, Module, RecurringWeeklyGoal, ReflectSettings, Task, Track,
    UpcomingBill, User, Vision, WeeklyPlan,
)
from plan_api import current_user


def stable_id(user_id: str, key: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"aniro-demo:{user_id}:{key}"))


def add_once(db, model, identifier: str, **values):
    item = db.get(model, identifier)
    if item is None:
        item = model(id=identifier, **values)
        db.add(item)
        db.flush()
    return item


def previous_month(value: date) -> date:
    return (value.replace(day=1) - timedelta(days=1)).replace(day=1)


def seed_demo(db, today: date | None = None):
    user = current_user(db)
    today = today or date.today()
    monday = today - timedelta(days=today.weekday())
    week = monday.isoformat()
    now = datetime.combine(today, time(12), tzinfo=timezone.utc)

    areas = {}
    for index, (key, name, color, icon) in enumerate((
        ("education", "Education", "bit", "book"),
        ("health", "Health & Living", "health", "heart"),
        ("career", "Career & Creation", "amber", "briefcase"),
        ("relationships", "Relationships", "rose", "users"),
    )):
        areas[key] = add_once(db, LifeArea, stable_id(user.id, f"area:{key}"), user_id=user.id,
                              name=f"Demo - {name}", color_key=color, icon_key=icon,
                              sort_order=index, archived_at=None)

    track_specs = (
        ("bit", "education", "BIT Degree", "bit"),
        ("english", "education", "Academic English", "violet"),
        ("fitness", "health", "Fitness & Energy", "health"),
        ("portfolio", "career", "Developer Portfolio", "amber"),
        ("family", "relationships", "Family & Friends", "rose"),
    )
    tracks = {}
    for index, (key, area_key, name, color) in enumerate(track_specs):
        tracks[key] = add_once(db, Track, stable_id(user.id, f"track:{key}"),
                               life_area_id=areas[area_key].id, name=f"Demo - {name}",
                               color_key=color, sort_order=index, archived_at=None)

    module_specs = (
        ("databases", "bit", "Database Systems"), ("networks", "bit", "Computer Networks"),
        ("web", "bit", "Web Development"), ("writing", "english", "Academic Writing"),
        ("strength", "fitness", "Strength Training"), ("case-study", "portfolio", "Portfolio Case Study"),
    )
    modules = {}
    for index, (key, track_key, name) in enumerate(module_specs):
        modules[key] = add_once(db, Module, stable_id(user.id, f"module:{key}"),
                                track_id=tracks[track_key].id, name=f"Demo - {name}",
                                status="active", sort_order=index, archived_at=None)

    long_vision = add_once(db, Vision, stable_id(user.id, "vision:degree"), user_id=user.id,
                           life_area_id=areas["education"].id, track_id=tracks["bit"].id,
                           module_id=None, parent_vision_id=None, horizon="3y",
                           title="Graduate with practical software skills",
                           description="Build strong fundamentals and a portfolio that demonstrates real work.",
                           status="active", target_date=None, sort_order=0, archived_at=None)
    add_once(db, Vision, stable_id(user.id, "vision:semester"), user_id=user.id,
             life_area_id=areas["education"].id, track_id=tracks["bit"].id,
             module_id=modules["databases"].id, parent_vision_id=long_vision.id, horizon="3mo",
             title="Complete the semester without last-minute studying",
             description="Use weekly review, spaced practice, and early assignment starts.",
             status="active", target_date=(today + timedelta(days=75)).isoformat(), sort_order=1, archived_at=None)
    add_once(db, Vision, stable_id(user.id, "vision:portfolio"), user_id=user.id,
             life_area_id=areas["career"].id, track_id=tracks["portfolio"].id,
             module_id=modules["case-study"].id, parent_vision_id=None, horizon="1y",
             title="Publish a portfolio that earns internship interviews", description="",
             status="active", target_date=None, sort_order=2, archived_at=None)
    add_once(db, Vision, stable_id(user.id, "vision:health"), user_id=user.id,
             life_area_id=areas["health"].id, track_id=tracks["fitness"].id,
             module_id=None, parent_vision_id=None, horizon="month",
             title="Keep steady energy through the exam month", description="",
             status="active", target_date=None, sort_order=3, archived_at=None)

    recurring = add_once(db, RecurringWeeklyGoal, stable_id(user.id, "recurring:database-review"),
                         user_id=user.id, module_id=modules["databases"].id,
                         starts_on=week, archived_at=None)
    goal_specs = (
        ("database", modules["databases"], "Finish SQL normalization exercises", "active", recurring.id),
        ("network", modules["networks"], "Review routing and subnetting", "active", None),
        ("portfolio", modules["case-study"], "Draft the dashboard case study", "active", None),
        ("health", modules["strength"], "Complete three short workouts", "completed", None),
    )
    goals = {}
    for index, (key, module, title, status, template_id) in enumerate(goal_specs):
        track = db.get(Track, module.track_id)
        area = db.get(LifeArea, track.life_area_id)
        goals[key] = add_once(db, Goal, stable_id(user.id, f"goal:{week}:{key}"), user_id=user.id,
                              life_area_id=area.id, track_id=track.id, module_id=module.id,
                              parent_vision_id=long_vision.id if key in ("database", "network") else None,
                              horizon="week", title=f"Demo - {title}", description="",
                              status=status, target_date=week, sort_order=index, archived_at=None,
                              recurring_template_id=template_id, recurrence_id=None,
                              recurrence_frequency=None, occurrence_date=None)

    plan_id = stable_id(user.id, f"plan:{week}")
    if db.get(WeeklyPlan, plan_id) is None and not db.scalar(select(WeeklyPlan).where(
            WeeklyPlan.user_id == user.id, WeeklyPlan.week_start == week)):
        db.add(WeeklyPlan(id=plan_id, user_id=user.id, week_start=week,
                          capacity_minutes=900, seasonal_priority="Prepare calmly for assessments"))

    task_specs = (
        ("sql", "database", "Complete SQL joins worksheet", "done", 60, 0),
        ("normalization", "database", "Practice normalization questions", "planned", 45, 1),
        ("subnet", "network", "Solve five subnetting problems", "partial", 50, 2),
        ("lecture", "network", "Watch routing lecture and take notes", "planned", 40, 3),
        ("case", "portfolio", "Write problem and solution sections", "planned", 75, 4),
        ("gym", "health", "Thirty-minute strength session", "done", 30, 5),
        ("capture", None, "Buy printer paper after class", "planned", 15, 6),
    )
    tasks = {}
    for key, goal_key, title, status, estimate, order in task_specs:
        goal = goals.get(goal_key) if goal_key else None
        module_id = goal.module_id if goal else None
        tasks[key] = add_once(db, Task, stable_id(user.id, f"task:{week}:{key}"), user_id=user.id,
                              goal_id=goal.id if goal else None, module_id=module_id, week_start=week,
                              title=f"Demo - {title}", status=status,
                              due_at=datetime.combine(monday + timedelta(days=min(order, 6)), time(18), tzinfo=timezone.utc),
                              estimate_minutes=estimate, sort_order=order, archived_at=None,
                              recurrence_id=stable_id(user.id, "task-series:lecture") if key == "lecture" else None,
                              recurrence_frequency="weekly" if key == "lecture" else None,
                              occurrence_date=(monday + timedelta(days=3)).isoformat() if key == "lecture" else None)

    block_specs = (
        ("sql", 0, 9, 60, "done"), ("normalization", 1, 14, 45, "planned"),
        ("subnet", 2, 10, 50, "partial"), ("lecture", 3, 16, 40, "planned"),
        ("case", 4, 11, 75, "planned"), ("gym", 5, 8, 30, "done"),
    )
    blocks = {}
    for key, day_offset, hour, minutes, status in block_specs:
        start = datetime.combine(monday + timedelta(days=day_offset), time(hour), tzinfo=timezone.utc)
        blocks[key] = add_once(db, CalendarBlock, stable_id(user.id, f"block:{week}:{key}"),
                               task_id=tasks[key].id, start_at=start, end_at=start + timedelta(minutes=minutes),
                               status=status, google_event_id=None, sync_state="local", archived_at=None)

    if db.get(FocusPreferences, user.id) is None:
        db.add(FocusPreferences(user_id=user.id, focus_minutes=25, short_break_minutes=5,
                                long_break_minutes=15, long_break_every=4,
                                sound=False, auto_transitions=False))
    focus_specs = (
        ("sql", 52, "done", "Joins became clearer after drawing the table relationships."),
        ("subnet", 34, "partial", "Need another pass on CIDR edge cases."),
        ("case", 46, "working", "Outlined the problem and added screenshots to review later."),
    )
    focus_sessions = {}
    for index, (task_key, minutes, result, note) in enumerate(focus_specs):
        ended = now - timedelta(days=index + 1, hours=2)
        started = ended - timedelta(minutes=minutes)
        focus_sessions[task_key] = add_once(
            db, FocusSession, stable_id(user.id, f"focus:{week}:{task_key}"), user_id=user.id,
            task_id=tasks[task_key].id, phase="summary", running=False, started_at=started,
            phase_started_at=None, ends_at=None, remaining_seconds=0, accrued_seconds=minutes * 60,
            gap_seconds=0, focus_intervals=max(1, minutes // 25), next_action="Review the next small step",
            return_instruction="", return_phase="focus", return_seconds=1500,
            distraction_note="Reply to the lecturer email\nCheck library opening hours",
            learning_checked=True, difficulty=result == "partial", recorded_minutes=minutes,
            result_status=result, result_note=note, version=3, ended_at=ended,
        )

    log_specs = (
        ("sql", blocks["sql"], focus_sessions["sql"], 52, "done", "Completed joins practice."),
        ("subnet", blocks["subnet"], focus_sessions["subnet"], 34, "partial", "Three of five problems completed."),
        ("case", None, focus_sessions["case"], 46, "partial", "Case study outline drafted."),
        ("gym", blocks["gym"], None, 30, "done", "Completed as planned."),
    )
    for key, block, focus, minutes, result, note in log_specs:
        add_once(db, CompletionLog, stable_id(user.id, f"completion:{week}:{key}"),
                 task_id=tasks[key].id, calendar_block_id=block.id if block else None,
                 focus_session_id=focus.id if focus else None, completed_minutes=minutes,
                 result=result, note=note, recorded_at=now - timedelta(days=1))

    habit_specs = (
        ("study", areas["education"], tracks["bit"], "Daily study review", "daily", "bit"),
        ("walk", areas["health"], tracks["fitness"], "Twenty-minute walk", "daily", "health"),
        ("plan", areas["career"], tracks["portfolio"], "Plan tomorrow's first task", "weekdays", "amber"),
    )
    habits = {}
    for key, area, track, name, frequency, color in habit_specs:
        habits[key] = add_once(db, Habit, stable_id(user.id, f"habit:{key}"), user_id=user.id,
                               life_area_id=area.id, track_id=track.id, name=f"Demo - {name}",
                               frequency_rule=frequency, color_key=color,
                               created_on=(today - timedelta(days=20)).isoformat(), archived_at=None)
    for key, habit in habits.items():
        for offset in range(14):
            check_date = today - timedelta(days=offset)
            if (key == "study" and offset not in (3, 8)) or (key == "walk" and offset % 3 != 0) or (key == "plan" and check_date.weekday() < 5 and offset not in (5,)):
                add_once(db, HabitCheckin, stable_id(user.id, f"checkin:{key}:{check_date}"),
                         habit_id=habit.id, local_date=check_date.isoformat(), status="done")

    for key, minutes in (("bit", 600), ("portfolio", 180), ("fitness", 120)):
        add_once(db, BalanceTarget, stable_id(user.id, f"track-target:{key}"), user_id=user.id,
                 track_id=tracks[key].id, target_minutes=minutes)
    for key, minutes in (("education", 720), ("career", 180), ("health", 150)):
        add_once(db, AreaBalanceTarget, stable_id(user.id, f"area-target:{key}"), user_id=user.id,
                 life_area_id=areas[key].id, target_minutes=minutes)
    if db.get(ReflectSettings, user.id) is None:
        db.add(ReflectSettings(user_id=user.id, coach_trigger_count=2))

    current_budget = db.scalar(select(BudgetMonth).where(BudgetMonth.user_id == user.id,
                                                         BudgetMonth.year == today.year,
                                                         BudgetMonth.month == today.month))
    if current_budget is None:
        current_budget = add_once(db, BudgetMonth, stable_id(user.id, f"budget:{today:%Y-%m}"),
                                  user_id=user.id, year=today.year, month=today.month,
                                  currency="LKR", limit_minor=5500000)
    prior = previous_month(today)
    prior_budget = db.scalar(select(BudgetMonth).where(BudgetMonth.user_id == user.id,
                                                       BudgetMonth.year == prior.year,
                                                       BudgetMonth.month == prior.month))
    if prior_budget is None:
        prior_budget = add_once(db, BudgetMonth, stable_id(user.id, f"budget:{prior:%Y-%m}"),
                                user_id=user.id, year=prior.year, month=prior.month,
                                currency="LKR", limit_minor=5000000)

    category_specs = (("Food & Dining", "health"), ("Housing", "lime"), ("Transport", "bit"),
                      ("Study", "violet"), ("Utilities", "amber"), ("Health", "health"),
                      ("Entertainment", "rose"))
    categories = {}
    for name, color in category_specs:
        category = db.scalar(select(ExpenseCategory).where(ExpenseCategory.user_id == user.id,
                                                           ExpenseCategory.name == name))
        categories[name] = category or add_once(db, ExpenseCategory, stable_id(user.id, f"category:{name}"),
                                                user_id=user.id, name=name, color_key=color, archived_at=None)

    accounts = {}
    for key, name, account_type, balance, color in (
        ("bank", "Demo - Main bank", "bank", 6850000, "bit"),
        ("cash", "Demo - Cash wallet", "cash", 485000, "lime"),
        ("ewallet", "Demo - E-wallet", "ewallet", 235000, "violet"),
    ):
        accounts[key] = add_once(db, FinancialAccount, stable_id(user.id, f"account:{key}"),
                                 user_id=user.id, name=name, account_type=account_type,
                                 balance_minor=balance, color_key=color, archived_at=None)

    for name, limit, essential in (("Housing", 1500000, True), ("Food & Dining", 1100000, True),
                                   ("Transport", 450000, True), ("Study", 500000, True),
                                   ("Entertainment", 350000, False)):
        envelope_id = stable_id(user.id, f"envelope:{today:%Y-%m}:{name}")
        existing = db.scalar(select(ExpenseEnvelope).where(ExpenseEnvelope.budget_month_id == current_budget.id,
                                                            ExpenseEnvelope.category_id == categories[name].id))
        if existing is None:
            add_once(db, ExpenseEnvelope, envelope_id, budget_month_id=current_budget.id,
                     category_id=categories[name].id, limit_minor=limit, essential=essential)

    bill_specs = (
        ("rent", "Boarding rent", 1200000, 2, "bank", True, True),
        ("internet", "Internet package", 180000, 29, "ewallet", True, False),
        ("phone", "Mobile plan", 95000, 30, "ewallet", True, False),
        ("course", "Online course installment", 420000, min(28, today.day + 2), "bank", False, False),
    )
    for key, name, amount, due_day, account_key, recurring_monthly, paid in bill_specs:
        due = today.replace(day=min(due_day, calendar.monthrange(today.year, today.month)[1])).isoformat()
        bill = add_once(db, UpcomingBill, stable_id(user.id, f"bill:{today:%Y-%m}:{key}"),
                        user_id=user.id, account_id=accounts[account_key].id, series_id=None,
                        name=f"Demo - {name}", amount_minor=amount, due_on=due,
                        recurring_monthly=recurring_monthly,
                        paid_at=now if paid else None, archived_at=None)
        bill.due_on = due
        bill.account_id = accounts[account_key].id
        bill.amount_minor = amount
        bill.paid_at = now if paid else None
        if recurring_monthly and bill.series_id is None:
            bill.series_id = bill.id

    current_expenses = (
        ("groceries", "Food & Dining", "bank", 148500, 1, "Weekly groceries"),
        ("bus", "Transport", "cash", 42000, 3, "Bus and tuk rides"),
        ("printing", "Study", "cash", 68500, 5, "Printing and stationery"),
        ("lunch", "Food & Dining", "ewallet", 78000, 7, "Lunch near campus"),
        ("medicine", "Health", "bank", 126000, 9, "Pharmacy"),
        ("movie", "Entertainment", "ewallet", 155000, 11, "Movie night"),
    )
    for key, category_name, account_key, amount, offset, description in current_expenses:
        spent = max(today.replace(day=1), today - timedelta(days=offset)).isoformat()
        add_once(db, Expense, stable_id(user.id, f"expense:{today:%Y-%m}:{key}"),
                 budget_month_id=current_budget.id, category_id=categories[category_name].id,
                 account_id=accounts[account_key].id, amount_minor=amount,
                 spent_on=spent, description=f"Demo - {description}")
    for index, (category_name, amount, description) in enumerate((
        ("Housing", 1200000, "Boarding rent"), ("Food & Dining", 575000, "Groceries and meals"),
        ("Transport", 195000, "Monthly travel"), ("Utilities", 265000, "Internet and phone"),
        ("Study", 330000, "Books and supplies"),
    )):
        add_once(db, Expense, stable_id(user.id, f"expense:{prior:%Y-%m}:summary:{index}"),
                 budget_month_id=prior_budget.id, category_id=categories[category_name].id,
                 account_id=None, amount_minor=amount, spent_on=prior.replace(day=3 + index * 5).isoformat(),
                 description=f"Demo - {description}")

    usage_id = {"user_id": user.id, "day": today.isoformat()}
    if db.get(CoachUsage, usage_id) is None:
        db.add(CoachUsage(user_id=user.id, day=today.isoformat(), request_count=2,
                          prompt_version="prd-v1", output_tokens=640))

    db.commit()
    seeded_models = (LifeArea, Track, Module, Vision, RecurringWeeklyGoal, Goal, WeeklyPlan, Task,
                     CalendarBlock, CompletionLog, FocusPreferences, FocusSession, Habit, HabitCheckin,
                     BalanceTarget, AreaBalanceTarget, ReflectSettings, BudgetMonth, ExpenseCategory,
                     FinancialAccount, ExpenseEnvelope, UpcomingBill, Expense, CoachUsage)
    return {model.__tablename__: db.scalar(select(func.count()).select_from(model)) for model in seeded_models}


if __name__ == "__main__":
    with SessionLocal() as session:
        counts = seed_demo(session)
    for table, count in counts.items():
        print(f"{table}: {count}")
