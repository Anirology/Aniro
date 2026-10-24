import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from db import Base
from models import Goal, LifeArea, Module, Track
from plan_api import (GoalCompletionIn, RecurringGoalsIn, add_recurring_goals,
                      complete_weekly_goal, current_user, plan, stop_recurring_goal)

WEEK = "2026-10-19"
NEXT = "2026-10-26"


class RecurringGoalTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        user = current_user(self.db)
        area = LifeArea(user_id=user.id, name="Education")
        self.db.add(area)
        self.db.flush()
        track = Track(life_area_id=area.id, name="BIT")
        self.db.add(track)
        self.db.flush()
        self.modules = [Module(track_id=track.id, name=name) for name in ("Programming", "Networks")]
        self.db.add_all(self.modules)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_each_week_is_independent_and_tasks_optional(self):
        add_recurring_goals(RecurringGoalsIn(week_start=WEEK, module_ids=[module.id for module in self.modules]), self.db)
        first = plan(WEEK, self.db)
        self.assertEqual(len(first["goals"]), 2)
        self.assertEqual(first["tasks"], [])
        self.assertEqual(first["goals"][0]["title"], "Finish this week’s Programming learning log")
        complete_weekly_goal(first["goals"][0]["id"], GoalCompletionIn(completed=True), self.db)
        self.assertEqual(plan(WEEK, self.db)["goals"][0]["status"], "completed")
        self.assertEqual(len(plan(WEEK, self.db)["goals"]), 2)
        next_week = plan(NEXT, self.db)
        self.assertEqual(len(next_week["goals"]), 2)
        self.assertTrue(all(goal["status"] == "active" for goal in next_week["goals"]))
        self.assertNotEqual(first["goals"][0]["id"], next_week["goals"][0]["id"])

    def test_existing_module_goal_is_reused_and_repeat_can_stop(self):
        module = self.modules[0]
        area_id = self.db.get(Track, module.track_id).life_area_id
        original = Goal(user_id=current_user(self.db).id, life_area_id=area_id,
                        track_id=module.track_id, module_id=module.id,
                        target_date=WEEK, title="My wording")
        self.db.add(original)
        self.db.commit()
        add_recurring_goals(RecurringGoalsIn(week_start=WEEK, module_ids=[module.id]), self.db)
        this_week = plan(WEEK, self.db)
        self.assertEqual(len(this_week["goals"]), 1)
        self.assertEqual(this_week["goals"][0]["id"], original.id)
        self.assertEqual(this_week["goals"][0]["title"], "My wording")
        template_id = this_week["goals"][0]["recurring_template_id"]
        stop_recurring_goal(template_id, self.db)
        self.assertEqual(plan(NEXT, self.db)["goals"], [])
        self.assertEqual(len(plan(WEEK, self.db)["goals"]), 1)

    def test_archiving_one_week_does_not_recreate_it(self):
        add_recurring_goals(RecurringGoalsIn(week_start=WEEK, module_ids=[self.modules[0].id]), self.db)
        goal_id = plan(WEEK, self.db)["goals"][0]["id"]
        from datetime import datetime, timezone
        goal = self.db.get(Goal, goal_id)
        goal.archived_at = datetime.now(timezone.utc)
        self.db.commit()
        self.assertEqual(len(plan(WEEK, self.db)["goals"]), 1)
        self.assertEqual(plan(WEEK, self.db)["goals"][0]["id"], goal_id)

    def test_rejects_unavailable_module(self):
        self.modules[0].status = "completed"
        self.db.commit()
        with self.assertRaises(HTTPException) as error:
            add_recurring_goals(RecurringGoalsIn(week_start=WEEK, module_ids=[self.modules[0].id]), self.db)
        self.assertEqual(error.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
