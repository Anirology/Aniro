import json
from datetime import date
from io import BytesIO
from pathlib import Path
from pypdf import PdfReader
from tests.test_stage3 import Stage3Tests
from stage3_api import export_weekly_pdf, set_budget, BudgetIn, add_category, CategoryIn, add_expense, ExpenseIn


class WeeklyReportTests(Stage3Tests):
    def test_week_crossing_months_excludes_outside_expenses(self):
        category = add_category(CategoryIn(name='Food & meals'), self.db)
        for month in ('2026-10', '2026-11'):
            set_budget(month, BudgetIn(limit_minor=1000000), self.db)
        for spent_on, amount in [('2026-10-25', 990000), ('2026-10-26', 12500), ('2026-11-01', 25000), ('2026-11-02', 880000)]:
            add_expense(ExpenseIn(category_id=category['id'], amount_minor=amount, spent_on=spent_on), self.db)
        response = export_weekly_pdf('2026-10-26', self.db)
        reader = PdfReader(BytesIO(response.body))
        text = '\n'.join(page.extract_text() for page in reader.pages)
        self.assertEqual(response.media_type, 'application/pdf')
        self.assertIn('LKR 375.00', text)
        self.assertIn('2026-10', text)
        self.assertIn('2026-11', text)
        self.assertIn('Food & meals', text)
        self.assertIn('Streak', text)
        self.assertGreaterEqual(len(reader.pages), 3)


if __name__ == '__main__':
    from db import SessionLocal
    with SessionLocal() as db:
        response = export_weekly_pdf('2026-10-26', db)
    destination = Path(__file__).resolve().parents[2] / 'output/pdf/aniro-weekly-2026-10-26.pdf'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(response.body)
    print(destination)
