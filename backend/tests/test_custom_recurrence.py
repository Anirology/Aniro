import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from db import Base
from main import GoalIn, add_goal, edit_goal
from models import LifeArea
from plan_api import TaskIn, add_task, current_user, plan


WEEK = "2026-10-26"
NEXT = "2026-11-02"


class CustomRecurrenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = current_user(self.db)
        self.area = LifeArea(user_id=self.user.id, name="Health")
        self.db.add(self.area)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_daily_goal_has_an_independent_occurrence_for_each_day(self):
        created = add_goal(GoalIn(life_area_id=self.area.id, title="Walk", target_date=WEEK,
                                  recurrence_frequency="daily"), self.db)
        this_week = plan(WEEK, self.db)["goals"]
        self.assertEqual(len(this_week), 7)
        self.assertEqual({goal["occurrence_date"] for goal in this_week},
                         {f"2026-10-{day}" for day in range(26, 32)} | {"2026-11-01"})

        edit_goal(created["id"], GoalIn(life_area_id=self.area.id, title="Walk",
                  target_date=WEEK, recurrence_frequency="weekly"), self.db)
        next_week = plan(NEXT, self.db)["goals"]
        self.assertEqual(len(next_week), 1)
        self.assertEqual(next_week[0]["occurrence_date"], NEXT)

    def test_daily_task_starts_on_its_due_date_and_keeps_the_due_time(self):
        due = datetime(2026, 10, 27, 8, 30, tzinfo=timezone.utc)
        add_task(TaskIn(week_start=WEEK, title="Review notes", due_at=due,
                        recurrence_frequency="daily"), self.db)
        tasks = plan(WEEK, self.db)["tasks"]
        self.assertEqual(len(tasks), 6)
        self.assertEqual(tasks[0]["occurrence_date"], "2026-10-27")
        self.assertTrue(all(task["due_at"].endswith("+00:00") for task in tasks))


if __name__ == "__main__":
    unittest.main()
