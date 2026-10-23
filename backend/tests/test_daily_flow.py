import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from db import Base
from models import CalendarBlock, CompletionLog, Task, User
from plan_api import QuickTaskIn, ReviewIn, ReviewItemIn, carryover_task, quick_task, review_blocks


class DailyFlowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.temporary.name) / 'aniro.db'}")

        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(timezone="Asia/Colombo")
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temporary.cleanup()

    def test_quick_capture_uses_current_local_week(self):
        task = quick_task(QuickTaskIn(title="  Read chapter  "), self.db)
        self.assertEqual(task["title"], "Read chapter")
        self.assertEqual(datetime.fromisoformat(task["week_start"]).weekday(), 0)
        with self.assertRaises(HTTPException):
            quick_task(QuickTaskIn(title="   "), self.db)

    def test_carryover_keeps_source_history_and_cannot_repeat(self):
        task = Task(user_id=self.user.id, week_start="2026-10-12", title="Draft outline")
        self.db.add(task)
        self.db.flush()
        start = datetime(2026, 10, 13, 9, tzinfo=timezone.utc).replace(tzinfo=None)
        block = CalendarBlock(task_id=task.id, start_at=start, end_at=start + timedelta(hours=1))
        self.db.add(block)
        self.db.commit()
        result = carryover_task(task.id, "2026-10-19", self.db)
        self.assertEqual(result["task"]["week_start"], "2026-10-19")
        self.assertEqual(result["source"]["status"], "moved")
        self.assertEqual(self.db.get(CalendarBlock, block.id).status, "moved")
        self.assertEqual(len(list(self.db.scalars(select(Task)))), 2)
        with self.assertRaises(HTTPException):
            carryover_task(task.id, "2026-10-19", self.db)

    def test_batch_review_records_done_and_skip_together(self):
        task = Task(user_id=self.user.id, week_start="2026-10-19", title="Study")
        self.db.add(task)
        self.db.flush()
        start = datetime(2026, 10, 20, 9)
        first = CalendarBlock(task_id=task.id, start_at=start, end_at=start + timedelta(hours=1))
        second = CalendarBlock(task_id=task.id, start_at=start + timedelta(hours=2), end_at=start + timedelta(hours=3))
        self.db.add_all([first, second])
        self.db.commit()
        result = review_blocks(ReviewIn(items=[
            ReviewItemIn(block_id=first.id, status="done"),
            ReviewItemIn(block_id=second.id, status="missed"),
        ]), self.db)
        self.assertEqual(result["reviewed"], 2)
        self.assertEqual(self.db.get(Task, task.id).status, "partial")
        self.assertEqual(sum(log.completed_minutes for log in self.db.scalars(select(CompletionLog))), 60)


if __name__ == "__main__":
    unittest.main()
