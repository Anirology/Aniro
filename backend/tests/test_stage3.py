import json
import unittest
from io import BytesIO
from datetime import date, datetime
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from pypdf import PdfReader
from db import Base
from models import LifeArea, Track, Module, Habit, HabitCheckin, ExpenseCategory, Expense, FinancialAccount, MoneyMovement
from plan_api import current_user, TaskIn, BlockIn, ResultIn, add_task, add_block, block_result
from main import GoalIn, VisionIn, add_goal, add_vision
from stage3_api import (streak_stats, reflect_summary, BudgetIn, CategoryIn, ExpenseIn, QuickExpenseIn,
                        set_budget, add_category, add_expense, add_expense_with_category, edit_expense, delete_expense,
                        money_summary, export_json, export_expenses_csv, export_expenses_pdf, TargetIn, set_area_target,
                        AccountIn, MoneyMovementIn, EnvelopeIn, BillIn, add_financial_account, add_money_movement,
                        set_expense_envelope, add_upcoming_bill, mark_upcoming_bill_paid)

WEEK = "2026-10-12"

class Stage3Tests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = current_user(self.db)
        self.area = LifeArea(user_id=self.user.id, name="Education", color_key="bit")
        self.db.add(self.area)
        self.db.flush()
        self.track = Track(life_area_id=self.area.id, name="BIT", color_key="bit")
        self.db.add(self.track)
        self.db.flush()
        self.module = Module(track_id=self.track.id, name="Mathematics")
        self.db.add(self.module)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_reflect_uses_recorded_minutes_and_waits_for_repeated_shortfall(self):
        vision = add_vision(VisionIn(life_area_id=self.area.id, horizon="3y", title="Build strong BIT foundations"), self.db)
        goal = add_goal(GoalIn(life_area_id=self.area.id, track_id=self.track.id,
                               module_id=self.module.id, parent_vision_id=vision["id"],
                               horizon="week", title="Review maths", target_date=WEEK), self.db)
        task = add_task(TaskIn(goal_id=goal["id"], week_start=WEEK, title="Past papers"), self.db)
        blocks = []
        for hour in (9, 11):
            blocks.append(add_block(BlockIn(task_id=task["id"],
                                      start_at=datetime.fromisoformat(f"2026-10-12T{hour:02d}:00:00+00:00"),
                                      end_at=datetime.fromisoformat(f"2026-10-12T{hour+1:02d}:00:00+00:00")), self.db))
        first = reflect_summary(self.db, WEEK, date(2026, 10, 18))
        self.assertEqual(first["totals"]["planned_minutes"], 120)
        self.assertEqual(first["totals"]["completed_minutes"], 0)
        self.assertEqual(first["modules"][0]["module_name"], "Mathematics")
        self.assertEqual(first["goals"][0]["vision_title"], vision["title"])
        self.assertEqual(first["goals"][0]["planned_minutes"], 120)
        self.assertEqual(first["goals"][0]["completed_minutes"], 0)
        block_result(blocks[0]["id"], ResultIn(status="partial", actual_minutes=20), self.db)
        one = reflect_summary(self.db, WEEK, date(2026, 10, 18))
        self.assertEqual(one["modules"][0]["completed_minutes"], 20)
        self.assertEqual(one["goals"][0]["completed_minutes"], 20)
        self.assertEqual(one["prompts"], [])
        block_result(blocks[1]["id"], ResultIn(status="missed"), self.db)
        two = reflect_summary(self.db, WEEK, date(2026, 10, 18))
        self.assertEqual(next(r for r in two["balance"] if r["scope"] == "track")["completed_minutes"], 20)
        set_area_target(self.area.id, TargetIn(target_minutes=180), self.db)
        area_row = next(r for r in reflect_summary(self.db, WEEK, date(2026, 10, 18))["balance"] if r["scope"] == "area")
        self.assertEqual(area_row["completed_minutes"], 20)
        self.assertEqual(area_row["target_minutes"], 180)
        self.assertEqual(len(two["prompts"]), 1)
        self.assertIn("120 minutes", two["prompts"][0]["text"])
        self.assertIn("20 minutes", two["prompts"][0]["text"])

    def test_habit_consistency_and_streak_use_explicit_checkins(self):
        habit = Habit(user_id=self.user.id, life_area_id=self.area.id, track_id=self.track.id,
                      name="BIT study", color_key="bit", created_on="2026-10-15", frequency_rule="daily")
        self.db.add(habit)
        self.db.flush()
        for local_date in ("2026-10-15", "2026-10-16", "2026-10-18"):
            self.db.add(HabitCheckin(habit_id=habit.id, local_date=local_date, status="done"))
        self.db.commit()
        summary = reflect_summary(self.db, WEEK, date(2026, 10, 18))
        self.assertEqual(summary["habits"][0]["consistency_pct"], 75)
        self.assertEqual(summary["habits"][0]["current_streak"], 1)
        self.assertEqual(summary["habits"][0]["color_key"], "bit")
        self.assertEqual(streak_stats(habit, {"2026-10-15", "2026-10-16"}, date(2026, 10, 18))["current_streak"], 0)

    def test_budget_totals_percentages_and_edit_delete(self):
        set_budget("2026-10", BudgetIn(limit_minor=4000000), self.db)
        category = add_category(CategoryIn(name="Food", color_key="health"), self.db)
        first = add_expense(ExpenseIn(category_id=category["id"], amount_minor=1200000,
                                      spent_on="2026-10-18", description="Groceries"), self.db)
        add_expense(ExpenseIn(category_id=category["id"], amount_minor=1000000,
                              spent_on="2026-10-18", description="Lunch"), self.db)
        initial = money_summary(self.db, "2026-10", date(2026, 10, 18))
        self.assertEqual(initial["spent_minor"], 2200000)
        self.assertEqual(initial["remaining_minor"], 1800000)
        self.assertEqual(initial["breakdown"][0]["percentage"], 100)
        edit_expense(first["id"], ExpenseIn(category_id=category["id"], amount_minor=3500000,
                                            spent_on="2026-10-18", description="Groceries"), self.db)
        changed = money_summary(self.db, "2026-10", date(2026, 10, 18))
        self.assertEqual(changed["remaining_minor"], -500000)
        self.assertTrue(changed["over_budget"])
        delete_expense(first["id"], True, self.db)
        self.assertEqual(money_summary(self.db, "2026-10", date(2026, 10, 18))["spent_minor"], 1000000)

    def test_first_expense_creates_category_only_when_budget_exists(self):
        payload = QuickExpenseIn(category_name="Study", amount_minor=12500,
                                 spent_on="2026-10-18", description="Notebook")
        with self.assertRaises(HTTPException):
            add_expense_with_category(payload, self.db)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ExpenseCategory)), 0)
        set_budget("2026-10", BudgetIn(limit_minor=4000000), self.db)
        created = add_expense_with_category(payload, self.db)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ExpenseCategory)), 1)
        self.assertEqual(self.db.get(Expense, created["id"]).amount_minor, 12500)
        self.assertEqual(money_summary(self.db, "2026-10", date(2026, 10, 18))["spent_minor"], 12500)

    def test_expense_pdf_is_branded_and_contains_monthly_records(self):
        set_budget("2026-10", BudgetIn(limit_minor=4000000), self.db)
        category = add_category(CategoryIn(name="Food", color_key="health"), self.db)
        add_expense(ExpenseIn(category_id=category["id"], amount_minor=125000,
                              spent_on="2026-10-18", description="Weekly groceries"), self.db)
        response = export_expenses_pdf("2026-10", self.db)
        self.assertEqual(response.media_type, "application/pdf")
        self.assertTrue(response.body.startswith(b"%PDF"))
        text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(response.body)).pages)
        self.assertIn("Aniro", text)
        self.assertIn("October 2026 expense report", text)
        self.assertIn("Weekly groceries", text)

    def test_student_money_tools_protect_essentials_and_update_balances(self):
        set_budget("2026-10", BudgetIn(limit_minor=4000000), self.db)
        category = add_category(CategoryIn(name="Food", color_key="health"), self.db)
        account = add_financial_account(AccountIn(name="Main bank", account_type="bank",
                                                   balance_minor=3000000, color_key="lime"), self.db)
        set_expense_envelope("2026-10", category["id"], EnvelopeIn(limit_minor=1000000, essential=True), self.db)
        bill = add_upcoming_bill(BillIn(name="Boarding rent", amount_minor=500000, due_on="2026-10-20",
                                        account_id=account["id"], recurring_monthly=True), self.db)
        expense = add_expense(ExpenseIn(category_id=category["id"], account_id=account["id"], amount_minor=200000,
                                        spent_on="2026-10-18", description="Groceries"), self.db)
        summary = money_summary(self.db, "2026-10", date(2026, 10, 18))
        self.assertEqual(summary["account_total_minor"], 2800000)
        self.assertEqual(summary["essential_reserved_minor"], 800000)
        self.assertEqual(summary["unpaid_bills_minor"], 500000)
        self.assertEqual(summary["safe_days"], 14)
        self.assertEqual(summary["safe_to_spend_minor"], 107142)
        self.assertEqual(summary["daily_spending"][17]["amount_minor"], 200000)
        self.assertEqual(summary["expenses"][0]["account_name"], "Main bank")
        mark_upcoming_bill_paid(bill["id"], True, self.db)
        self.assertEqual(money_summary(self.db, "2026-10", date(2026, 10, 18))["safe_to_spend_minor"], 142857)
        delete_expense(expense["id"], True, self.db)
        self.assertEqual(self.db.get(FinancialAccount, account["id"]).balance_minor, 3000000)

    def test_income_and_transfer_keep_account_math_auditable(self):
        bank = add_financial_account(AccountIn(name="Main bank", account_type="bank",
                                               balance_minor=1000000, color_key="lime"), self.db)
        wallet = add_financial_account(AccountIn(name="Cash wallet", account_type="cash",
                                                 balance_minor=100000, color_key="health"), self.db)
        add_money_movement(MoneyMovementIn(kind="income", amount_minor=500000,
                                           destination_account_id=bank["id"], source_label="Parents",
                                           occurred_on="2026-10-18", note="Monthly support"), self.db)
        add_money_movement(MoneyMovementIn(kind="transfer", amount_minor=200000,
                                           source_account_id=bank["id"], destination_account_id=wallet["id"],
                                           occurred_on="2026-10-19", note="Cash withdrawal"), self.db)
        summary = money_summary(self.db, "2026-10", date(2026, 10, 19))
        self.assertEqual(self.db.get(FinancialAccount, bank["id"]).balance_minor, 1300000)
        self.assertEqual(self.db.get(FinancialAccount, wallet["id"]).balance_minor, 300000)
        self.assertEqual(summary["account_total_minor"], 1600000)
        self.assertEqual([row["kind"] for row in summary["movements"]], ["transfer", "income"])
        self.assertEqual(summary["movements"][0]["source_name"], "Main bank")
        self.assertEqual(summary["movements"][0]["destination_name"], "Cash wallet")
        self.assertEqual(summary["movements"][1]["source_name"], "Parents")
        self.assertEqual(self.db.scalar(select(func.count()).select_from(MoneyMovement)), 2)

    def test_fresh_reflect_money_and_exports_contain_no_examples(self):
        reflect = reflect_summary(self.db, WEEK, date(2026, 10, 18))
        money = money_summary(self.db, "2026-10", date(2026, 10, 18))
        backup = json.loads(export_json(self.db).body)
        csv_text = export_expenses_csv("2026-10", self.db).body.decode()
        self.assertEqual(reflect["habits"], [])
        self.assertEqual(reflect["modules"], [])
        self.assertIsNone(money["budget"])
        self.assertEqual(money["categories"], [])
        self.assertEqual(backup["tables"]["habits"], [])
        self.assertEqual(backup["tables"]["expenses"], [])
        self.assertEqual(csv_text.splitlines(), ["id,date,month,category,amount_lkr,description"])

if __name__ == "__main__":
    unittest.main()
