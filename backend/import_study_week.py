"""Link an existing week's Google study events to one Aniro task per block.

Run from the repository root with backend/.venv/Scripts/python.exe
backend/import_study_week.py YYYY-MM-DD [--apply]. Without --apply, preview only.
Google Calendar is read through the running local API; this script never writes to it.
"""

import argparse
import json
from datetime import datetime, timezone
from urllib.request import urlopen

from sqlalchemy import select

from db import SessionLocal
from models import CalendarBlock, Goal, Module, Task, User


SUBJECTS = {
    "Maths": "Mathematics",
    "Programming": "Programming",
    "Computer Systems": "Computer Systems",
    "Web Development": "Web Development",
    "ICT Skills": "ICT Skills and Application",
    "Communication": "Communication",
}


def study_event(event):
    if event.get("all_day") or not event.get("start") or not event.get("end"):
        return None
    title = event.get("title", "")
    for subject, module_name in SUBJECTS.items():
        if title.startswith(subject + " — ") or (" " + subject + " — ") in title:
            return module_name, title[title.index(subject):]
    return None


def utc_naive(value):
    return datetime.fromisoformat(value).astimezone(timezone.utc).replace(tzinfo=None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("week", help="Monday in YYYY-MM-DD format")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if datetime.fromisoformat(args.week).weekday() != 0:
        parser.error("week must be a Monday")
    with urlopen(f"http://127.0.0.1:8000/api/integrations/google/events?week={args.week}", timeout=30) as response:
        events = json.load(response)["events"]

    with SessionLocal() as db:
        user = db.scalar(select(User).limit(1))
        if not user:
            raise RuntimeError("Aniro user is missing")
        goals = list(db.scalars(select(Goal).where(Goal.user_id == user.id, Goal.target_date == args.week,
                                                    Goal.horizon == "week", Goal.archived_at.is_(None))))
        modules = {module.id: module for module in db.scalars(select(Module))}
        by_module = {modules[goal.module_id].name: goal for goal in goals if goal.module_id in modules}
        linked = set(db.scalars(select(CalendarBlock.google_event_id).where(CalendarBlock.google_event_id.is_not(None))))
        prepared = []
        for event in events:
            match = study_event(event)
            if not match:
                continue
            module_name, title = match
            if module_name not in by_module:
                raise RuntimeError(f"No weekly goal for {module_name}")
            if not event.get("id"):
                raise RuntimeError(f"Google event lacks an ID: {title}")
            if event["id"] in linked:
                continue
            start, end = utc_naive(event["start"]), utc_naive(event["end"])
            if start >= end or (end - start).total_seconds() > 86400:
                raise RuntimeError(f"Invalid event interval: {title}")
            prepared.append((event, by_module[module_name], title, start, end))
        print(f"Study events: {sum(bool(study_event(e)) for e in events)}; already linked: "
              f"{sum(bool(study_event(e)) and e.get('id') in linked for e in events)}; to add: {len(prepared)}")
        for event, goal, title, start, end in prepared:
            print(f"{event['start'][:16]}  {title}  -> {modules[goal.module_id].name}")
        if not args.apply:
            return
        for event, goal, title, start, end in prepared:
            task = Task(user_id=user.id, goal_id=goal.id, module_id=goal.module_id,
                        week_start=args.week, title=title, status="planned",
                        estimate_minutes=round((end - start).total_seconds() / 60))
            db.add(task)
            db.flush()
            db.add(CalendarBlock(task_id=task.id, start_at=start, end_at=end,
                                 status="planned", google_event_id=event["id"], sync_state="imported"))
        db.commit()
        print(f"Added {len(prepared)} tasks and linked blocks. Google events unchanged.")


if __name__ == "__main__":
    main()
