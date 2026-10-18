import unittest
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import create_engine, event, select, func
from sqlalchemy.orm import Session
from db import Base
from models import LifeArea, Track, Module, Task
from main import GoalIn, add_goal
from plan_api import TaskIn, BlockIn, TaskBlockIn, ResultIn, add_task, add_block, add_task_block, block_result, task_result, completion_totals, plan

WEEK = "2026-10-12"

class Stage2Tests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.area = LifeArea(user_id=self._user_id(), name="Education", color_key="bit")
        self.db.add(self.area)
        self.db.flush()
        self.track = Track(life_area_id=self.area.id, name="BIT", color_key="bit")
        self.db.add(self.track)
        self.db.flush()
        self.module = Module(track_id=self.track.id, name="Mathematics")
        self.db.add(self.module)
        self.db.commit()
        self.goal = add_goal(GoalIn(life_area_id=self.area.id, track_id=self.track.id, module_id=self.module.id, horizon="week", title="Revise Mathematics", target_date=WEEK), self.db)

    def _user_id(self):
        from plan_api import current_user
        return current_user(self.db).id

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_goal_task_link_and_breadcrumb(self):
        task = add_task(TaskIn(goal_id=self.goal["id"], week_start=WEEK, title="Solve past papers", estimate_minutes=60), self.db)
        self.assertEqual(task["goal_id"], self.goal["id"])
        self.assertEqual(task["module_id"], self.module.id)
        response = plan(WEEK, self.db)
        self.assertEqual(response["goals"][0]["breadcrumb"], "Education → BIT → Mathematics")
        with self.assertRaises(HTTPException) as error:
            add_task(TaskIn(goal_id=self.goal["id"], week_start="2026-10-19", title="Wrong week"), self.db)
        self.assertEqual(error.exception.status_code, 422)

    def test_only_recorded_work_counts_and_undo_corrects_totals(self):
        task = add_task(TaskIn(goal_id=self.goal["id"], week_start=WEEK, title="Solve past papers", estimate_minutes=60), self.db)
        block = add_block(BlockIn(task_id=task["id"], start_at=datetime.fromisoformat("2026-10-12T09:00:00+00:00"), end_at=datetime.fromisoformat("2026-10-12T10:00:00+00:00")), self.db)
        self.assertEqual(completion_totals(self.db, self._user_id(), WEEK)["planned_minutes"], 60)
        self.assertEqual(completion_totals(self.db, self._user_id(), WEEK)["completed_minutes"], 0)
        block_result(block["id"], ResultIn(status="partial", actual_minutes=25, note="Short session"), self.db)
        self.assertEqual(completion_totals(self.db, self._user_id(), WEEK)["completed_minutes"], 25)
        block_result(block["id"], ResultIn(status="done", actual_minutes=45), self.db)
        self.assertEqual(completion_totals(self.db, self._user_id(), WEEK)["completed_minutes"], 45)
        self.assertEqual(completion_totals(self.db, self._user_id(), WEEK)["completed_tasks"], 1)
        task_result(task["id"], ResultIn(status="planned"), self.db)
        self.assertEqual(completion_totals(self.db, self._user_id(), WEEK)["completed_minutes"], 0)

    def test_slot_creates_linked_task_and_block_without_orphan_on_conflict(self):
        first = add_task_block(TaskBlockIn(title="Math practice", goal_id=self.goal["id"], week_start=WEEK,
                       start_at=datetime.fromisoformat("2026-10-12T09:00:00+00:00"),
                       end_at=datetime.fromisoformat("2026-10-12T10:00:00+00:00")),self.db)
        self.assertEqual(first["task"]["module_id"],self.module.id)
        self.assertEqual(first["block"]["task_id"],first["task"]["id"])
        with self.assertRaises(HTTPException) as conflict:
            add_task_block(TaskBlockIn(title="Overlapping task", week_start=WEEK,
                           start_at=datetime.fromisoformat("2026-10-12T09:30:00+00:00"),
                           end_at=datetime.fromisoformat("2026-10-12T10:30:00+00:00")),self.db)
        self.assertEqual(conflict.exception.status_code,409)
        self.db.rollback()
        self.assertEqual(self.db.scalar(select(func.count(Task.id))),1)

if __name__ == "__main__":
    unittest.main()
