import json
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from db import Base
from models import User, LifeArea, Vision, BudgetMonth, ExpenseCategory, Expense
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


if __name__ == "__main__":
    unittest.main()
