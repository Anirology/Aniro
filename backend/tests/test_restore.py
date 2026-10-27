import json
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from db import Base
from models import User, LifeArea, Track, Module, Vision, Goal, RecurringWeeklyGoal, BudgetMonth, ExpenseCategory, Expense
from stage3_api import export_json, preview_backup, restore_backup


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "aniro.db"
        self.engine = create_engine(f"sqlite:///{self.path}")

        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User()
        self.db.add(self.user)
        self.db.flush()
        self.area = LifeArea(user_id=self.user.id, name="Education")
        self.db.add(self.area)
        self.db.flush()
        parent = Vision(user_id=self.user.id, life_area_id=self.area.id, horizon="10y", title="Learn")
        self.db.add(parent)
        self.db.flush()
        self.db.add(Vision(user_id=self.user.id, life_area_id=self.area.id,
                           parent_vision_id=parent.id, horizon="1y", title="Practise"))
        budget = BudgetMonth(user_id=self.user.id, year=2026, month=10, currency="LKR", limit_minor=4000000)
        category = ExpenseCategory(user_id=self.user.id, name="Study")
        self.db.add_all([budget, category])
        self.db.flush()
        self.db.add(Expense(budget_month_id=budget.id, category_id=category.id,
                            amount_minor=25000, spent_on="2026-10-23", description="Book"))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temporary.cleanup()

    def test_restore_replaces_records_and_snapshots_previous_database(self):
        exported = json.loads(export_json(self.db).body)
        self.assertGreater(preview_backup(exported)["records"], 0)
        self.area.name = "Changed after export"
        self.db.commit()
        result = restore_backup(exported, True, self.db)
        self.db.expire_all()
        self.assertEqual(self.db.get(LifeArea, self.area.id).name, "Education")
        self.assertEqual(len(list(self.db.scalars(select(Vision)))), 2)
        self.assertEqual(len(list(self.db.scalars(select(Expense)))), 1)
        self.assertTrue(Path(result["local_snapshot"]).exists())

    def test_invalid_backup_cannot_replace_data(self):
        exported = json.loads(export_json(self.db).body)
        exported["tables"]["life_areas"][0]["user_id"] = "other-user"
        with self.assertRaises(HTTPException):
            restore_backup(exported, True, self.db)
        self.assertEqual(self.db.get(LifeArea, self.area.id).name, "Education")
        self.assertFalse((self.path.parent / "backups").exists())

    def test_recurring_goals_survive_export_and_legacy_backup_still_restores(self):
        track = Track(life_area_id=self.area.id, name="BIT")
        self.db.add(track)
        self.db.flush()
        module = Module(track_id=track.id, name="Programming")
        self.db.add(module)
        self.db.flush()
        template = RecurringWeeklyGoal(user_id=self.user.id, module_id=module.id, starts_on="2026-10-19")
        self.db.add(template)
        self.db.flush()
        goal = Goal(user_id=self.user.id, life_area_id=self.area.id, track_id=track.id,
                    module_id=module.id, recurring_template_id=template.id,
                    target_date="2026-10-19", title="Learning log")
        self.db.add(goal)
        self.db.commit()
        exported = json.loads(export_json(self.db).body)
        self.assertEqual(len(exported["tables"]["recurring_weekly_goals"]), 1)
        restore_backup(exported, True, self.db)
        self.db.expire_all()
        self.assertEqual(self.db.get(Goal, goal.id).recurring_template_id, template.id)
        legacy = json.loads(json.dumps(exported))
        del legacy["tables"]["recurring_weekly_goals"]
        for row in legacy["tables"]["goals"]:
            del row["recurring_template_id"]
            del row["recurrence_id"]
            del row["recurrence_frequency"]
            del row["occurrence_date"]
        for row in legacy["tables"]["tasks"]:
            del row["recurrence_id"]
            del row["recurrence_frequency"]
            del row["occurrence_date"]
        self.assertGreater(preview_backup(legacy)["records"], 0)
        restore_backup(legacy, True, self.db)
        self.db.expire_all()
        self.assertIsNone(self.db.get(Goal, goal.id).recurring_template_id)


if __name__ == "__main__":
    unittest.main()
