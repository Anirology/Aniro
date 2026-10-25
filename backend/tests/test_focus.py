import unittest
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from db import Base
from focus_api import ActionIn, CorrectIn, RecordIn, StartIn, action, correct, get_focus, history, record, start
from models import CompletionLog, FocusSession, Task
from plan_api import ResultIn, current_user, plan, task_result
from stage3_api import reflect_summary


class FocusTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        @event.listens_for(self.engine, "connect")
        def keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = current_user(self.db)
        self.task = Task(user_id=self.user.id, title="Review BIT notes", week_start="2026-10-26", estimate_minutes=40)
        self.db.add(self.task)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_work_is_explicit_and_preserved_by_task_result(self):
        state = start(StartIn(task_id=self.task.id), self.db)
        item = state["session"]
        self.assertEqual(item["task"]["id"], self.task.id)
        self.assertEqual(item["next_action"], self.task.title)
        self.assertEqual(len(plan("2026-10-26", self.db)["tasks"]), 1)
        self.db.rollback()
        self.assertEqual(self.db.get(Task, self.task.id).status, "planned")
        self.db.rollback()
        paused = action(ActionIn(version=item["version"], action="pause"), self.db)["session"]
        self.assertFalse(paused["running"])
        with self.assertRaises(HTTPException) as stale:
            action(ActionIn(version=item["version"], action="end"), self.db)
        self.assertEqual(stale.exception.status_code, 409)
        self.db.rollback()
        resumed = action(ActionIn(version=paused["version"], action="resume"), self.db)["session"]
        summary = action(ActionIn(version=resumed["version"], action="end"), self.db)["session"]
        self.assertEqual(self.db.get(Task, self.task.id).status, "planned")
        record(RecordIn(version=summary["version"], recorded_minutes=12, status="working", note="Revised two topics"), self.db)
        self.assertEqual(self.db.get(Task, self.task.id).status, "planned")
        self.assertEqual(plan("2026-10-26", self.db)["totals"]["completed_minutes"], 12)
        self.assertEqual(reflect_summary(self.db, "2026-10-26")["totals"]["completed_minutes"], 12)
        task_result(self.task.id, ResultIn(status="done"), self.db)
        self.assertEqual(len(list(self.db.scalars(select(CompletionLog).where(CompletionLog.focus_session_id.is_not(None))))), 1)
        self.assertEqual(plan("2026-10-26", self.db)["totals"]["completed_minutes"], 12)

    def test_break_and_two_minute_return_retain_task(self):
        first = start(StartIn(task_id=self.task.id, starter=True), self.db)["session"]
        session = self.db.get(FocusSession, first["id"])
        session.phase_started_at = datetime.now(timezone.utc) - timedelta(minutes=3)
        session.ends_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        self.db.commit()
        focus = action(ActionIn(version=first["version"], action="focus"), self.db)["session"]
        self.assertEqual(focus["task_id"], self.task.id)
        self.assertGreaterEqual(focus["recordable_minutes"], 2)
        pause = action(ActionIn(version=focus["version"], action="one_minute_pause"), self.db)["session"]
        self.assertEqual(pause["task_id"], self.task.id)
        session = self.db.get(FocusSession, first["id"])
        session.ends_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.db.commit()
        resumed = action(ActionIn(version=pause["version"], action="resume"), self.db)["session"]
        self.assertEqual(resumed["phase"], "focus")
        brk = action(ActionIn(version=resumed["version"], action="short_break", return_instruction="Open chapter 3"), self.db)["session"]
        self.assertEqual(brk["return_instruction"], "Open chapter 3")
        self.assertEqual(brk["task_id"], self.task.id)

    def test_correction_updates_same_attempt(self):
        first = start(StartIn(task_id=self.task.id), self.db)["session"]
        summary = action(ActionIn(version=first["version"], action="end"), self.db)["session"]
        record(RecordIn(version=summary["version"], recorded_minutes=20, status="done"), self.db)
        correct(first["id"], CorrectIn(recorded_minutes=15, status="partial", note="Still revising"), self.db)
        logs = list(self.db.scalars(select(CompletionLog).where(CompletionLog.focus_session_id == first["id"])))
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].completed_minutes, 15)
        self.assertEqual(self.db.get(Task, self.task.id).status, "partial")
        self.assertEqual(len(history(self.db)), 1)
        correct(first["id"], CorrectIn(recorded_minutes=15, status="working", note="Continuing"), self.db)
        self.assertEqual(self.db.get(Task, self.task.id).status, "planned")
        self.assertEqual(plan("2026-10-26", self.db)["totals"]["completed_minutes"], 15)

    def test_unlinked_record_is_visible_in_reflect(self):
        first = start(StartIn(starter=True), self.db)["session"]
        summary = action(ActionIn(version=first["version"], action="end"), self.db)["session"]
        record(RecordIn(version=summary["version"], recorded_minutes=2, status="working"), self.db)
        result = reflect_summary(self.db, "2026-10-26", today_override=datetime(2026, 10, 26).date())
        self.assertEqual(result["totals"]["completed_minutes"], 2)
        self.assertEqual(result["focus_records"][0]["task_id"], None)
        correct(first["id"], CorrectIn(task_id=self.task.id, recorded_minutes=2, status="partial"), self.db)
        self.assertEqual(plan("2026-10-26", self.db)["totals"]["completed_minutes"], 2)
        self.assertEqual(reflect_summary(self.db, "2026-10-26")["totals"]["completed_minutes"], 2)


if __name__ == "__main__":
    unittest.main()
