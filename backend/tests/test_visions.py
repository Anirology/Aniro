import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from db import Base
from main import VisionIn, GoalIn, add_vision, add_goal, archive, delete, overview
from models import LifeArea, Vision, Goal
from plan_api import current_user, plan


class VisionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        area = LifeArea(user_id=current_user(self.db).id, name="Education")
        self.db.add(area)
        self.db.commit()
        self.area_id = area.id

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_visions_are_separate_from_weekly_goals_and_keep_links(self):
        long = add_vision(VisionIn(life_area_id=self.area_id, horizon="10y", title="Learn deeply"), self.db)
        short = add_vision(VisionIn(life_area_id=self.area_id, horizon="3y", title="Finish degree", parent_vision_id=long["id"]), self.db)
        goal = add_goal(GoalIn(life_area_id=self.area_id, title="Study this week", target_date="2026-10-12", parent_vision_id=short["id"]), self.db)
        self.assertEqual({v["id"] for v in overview(self.db)["visions"]}, {long["id"], short["id"]})
        self.assertEqual([g["id"] for g in overview(self.db)["goals"]], [goal["id"]])
        self.assertEqual({v["id"] for v in plan("2026-10-12", self.db)["visions"]}, {long["id"], short["id"]})
        self.assertEqual(self.db.scalar(select(Goal).where(Goal.id == goal["id"])).parent_vision_id, short["id"])
        with self.assertRaises(HTTPException) as rejected:
            delete("visions", short["id"], True, self.db)
        self.assertEqual(rejected.exception.status_code, 409)
        archive("visions", short["id"], db=self.db)
        self.assertIsNotNone(self.db.get(Vision, short["id"]).archived_at)
        archive("visions", short["id"], restore=True, db=self.db)
        self.assertIsNone(self.db.get(Vision, short["id"]).archived_at)

    def test_horizon_types_cannot_cross_tables(self):
        with self.assertRaises(ValueError):
            VisionIn(life_area_id=self.area_id, horizon="week", title="Wrong")
        with self.assertRaises(ValueError):
            GoalIn(life_area_id=self.area_id, horizon="10y", title="Wrong", target_date="2026-10-12")

    def test_weekly_goal_cannot_link_to_vision_in_another_area(self):
        other = LifeArea(user_id=current_user(self.db).id, name="Health")
        self.db.add(other)
        self.db.commit()
        vision = add_vision(VisionIn(life_area_id=other.id, horizon="5y", title="Stay healthy"), self.db)
        with self.assertRaises(HTTPException) as rejected:
            add_goal(GoalIn(life_area_id=self.area_id, title="Study", target_date="2026-10-12", parent_vision_id=vision["id"]), self.db)
        self.assertEqual(rejected.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
