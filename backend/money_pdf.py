"""Branded PDF reporting for the Money workspace."""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Flowable, Frame, KeepTogether, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent
INK = colors.HexColor("#202A21")
MUTED = colors.HexColor("#6D786B")
GREEN = colors.HexColor("#78A94B")
PALE_GREEN = colors.HexColor("#EFF6E5")
LINE = colors.HexColor("#DDE5D7")
PAPER = colors.HexColor("#FAFCF8")
RED = colors.HexColor("#B4513B")
TONES = {
    "lime": colors.HexColor("#86B95A"), "health": colors.HexColor("#6FAF88"),
    "bit": colors.HexColor("#668FBB"), "amber": colors.HexColor("#D5A34E"),
    "rose": colors.HexColor("#C77B76"), "violet": colors.HexColor("#8C7BB5"),
}


def _register_fonts():
    for name, filename in (("Jakarta", "PlusJakartaSans-400.ttf"),
                           ("Jakarta-Bold", "PlusJakartaSans-700.ttf"),
                           ("Jakarta-ExtraBold", "PlusJakartaSans-800.ttf")):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, ROOT / "assets" / filename))


def _money(minor: int | None) -> str:
    if minor is None:
        return "Not set"
    return f"LKR {minor / 100:,.2f}"


class CategoryBars(Flowable):
    def __init__(self, rows: list[dict], width: float):
        super().__init__()
        self.rows = rows[:7]
        self.width = width
        self.height = max(34, len(self.rows) * 28 + 6)

    def draw(self):
        if not self.rows:
            self.canv.setFillColor(MUTED)
            self.canv.setFont("Jakarta", 8.5)
            self.canv.drawString(0, 12, "No category spending was recorded for this month.")
            return
        largest = max(row["amount_minor"] for row in self.rows) or 1
        for index, row in enumerate(self.rows):
            y = self.height - 19 - index * 28
            tone = TONES.get(row.get("color_key"), GREEN)
            self.canv.setFillColor(INK)
            self.canv.setFont("Jakarta-Bold", 8.2)
            self.canv.drawString(0, y + 7, row["name"][:30])
            self.canv.setFillColor(MUTED)
            self.canv.setFont("Jakarta", 7.6)
            self.canv.drawRightString(self.width, y + 7, _money(row["amount_minor"]))
            self.canv.setFillColor(colors.HexColor("#E9EEE5"))
            self.canv.roundRect(0, y - 2, self.width, 6, 3, fill=1, stroke=0)
            self.canv.setFillColor(tone)
            self.canv.roundRect(0, y - 2, max(4, self.width * row["amount_minor"] / largest), 6, 3, fill=1, stroke=0)


def build_expense_pdf(summary: dict, display_name: str = "") -> bytes:
    _register_fonts()
    output = BytesIO()
    month_label = datetime.strptime(summary["month"], "%Y-%m").strftime("%B %Y")
    doc = BaseDocTemplate(output, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
                          topMargin=31 * mm, bottomMargin=20 * mm,
                          title=f"Aniro - {month_label} expense report",
                          author=display_name or "Aniro")
    styles = getSampleStyleSheet()
    title = ParagraphStyle("Title", parent=styles["Title"], fontName="Jakarta-ExtraBold",
                           fontSize=22, leading=27, textColor=INK, alignment=TA_LEFT, spaceAfter=4)
    subtitle = ParagraphStyle("Subtitle", parent=styles["Normal"], fontName="Jakarta",
                              fontSize=8.5, leading=13, textColor=MUTED)
    section = ParagraphStyle("Section", parent=styles["Heading2"], fontName="Jakarta-Bold",
                             fontSize=11, leading=15, textColor=INK, spaceBefore=15, spaceAfter=8)
    cell = ParagraphStyle("Cell", parent=styles["Normal"], fontName="Jakarta",
                          fontSize=7.6, leading=10.5, textColor=INK)
    cell_bold = ParagraphStyle("CellBold", parent=cell, fontName="Jakarta-Bold")
    cell_right = ParagraphStyle("CellRight", parent=cell_bold, alignment=TA_RIGHT)
    header_cell = ParagraphStyle("HeaderCell", parent=cell_bold, textColor=colors.white)
    header_right = ParagraphStyle("HeaderRight", parent=header_cell, alignment=TA_RIGHT)
    story = [Paragraph(f"{month_label} expense report", title),
             Paragraph(f"A clear monthly record of spending, categories, and budget performance. Generated {datetime.now(timezone.utc).strftime('%d %B %Y at %H:%M UTC')}.", subtitle),
             Spacer(1, 8 * mm)]

    remaining = summary.get("remaining_minor")
    cards = [[Paragraph("MONTHLY BUDGET", cell_bold), Paragraph("TOTAL SPENT", cell_bold),
              Paragraph("BUDGET LEFT" if not summary.get("over_budget") else "OVER BUDGET", cell_bold)],
             [Paragraph(_money(summary.get("budget", {}).get("limit_minor") if summary.get("budget") else None),
                        ParagraphStyle("CardValue", parent=cell_bold, fontSize=13, leading=17)),
              Paragraph(_money(summary.get("spent_minor", 0)), ParagraphStyle("CardValue2", parent=cell_bold, fontSize=13, leading=17)),
              Paragraph(_money(abs(remaining)) if remaining is not None else "Not set",
                        ParagraphStyle("CardValue3", parent=cell_bold, fontSize=13, leading=17,
                                       textColor=RED if summary.get("over_budget") else INK))]]
    card_table = Table(cards, colWidths=[doc.width / 3] * 3, rowHeights=[8 * mm, 13 * mm])
    card_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE_GREEN), ("BOX", (0, 0), (-1, -1), .7, LINE),
        ("INNERGRID", (0, 0), (-1, -1), .5, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    breakdown = summary.get("breakdown", [])
    expenses = summary.get("expenses", [])
    largest = max(breakdown, key=lambda row: row["amount_minor"], default=None)
    average = summary.get("spent_minor", 0) // len(expenses) if expenses else 0
    facts = Table([
        [Paragraph("TRANSACTIONS", cell_bold), Paragraph("AVERAGE EXPENSE", cell_bold), Paragraph("LARGEST CATEGORY", cell_bold)],
        [Paragraph(str(len(expenses)), cell_bold), Paragraph(_money(average), cell_bold),
         Paragraph(escape(largest["name"]) if largest else "No spending", cell_bold)],
    ], colWidths=[doc.width / 3] * 3)
    facts.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .6, LINE), ("INNERGRID", (0, 0), (-1, -1), .4, LINE),
        ("BACKGROUND", (0, 0), (-1, 0), PAPER), ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([card_table, Paragraph("Spending by category", section),
                  CategoryBars(breakdown, doc.width), Paragraph("Monthly snapshot", section), facts, PageBreak(),
                  Paragraph("Expense history", title),
                  Paragraph(f"Every expense recorded during {month_label}, ordered from newest to oldest.", subtitle),
                  Spacer(1, 5 * mm)])

    table_rows = [[Paragraph("DATE", header_cell), Paragraph("DESCRIPTION", header_cell),
                   Paragraph("CATEGORY", header_cell), Paragraph("PAID FROM", header_cell),
                   Paragraph("AMOUNT", header_right)]]
    for expense in summary.get("expenses", []):
        description = escape(expense.get("description") or "Expense")
        table_rows.append([
            Paragraph(escape(expense["spent_on"]), cell), Paragraph(description, cell_bold),
            Paragraph(escape(expense.get("category_name") or "Uncategorized"), cell),
            Paragraph(escape(expense.get("account_name") or "Unlinked"), cell),
            Paragraph(_money(expense["amount_minor"]), cell_right),
        ])
    if len(table_rows) == 1:
        table_rows.append([Paragraph("No expenses were recorded for this month.", cell), "", "", "", ""])
    expense_table = Table(table_rows, repeatRows=1,
                          colWidths=[24 * mm, 56 * mm, 31 * mm, 29 * mm, 34 * mm])
    expense_style = [
        ("BACKGROUND", (0, 0), (-1, 0), INK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("LINEBELOW", (0, 1), (-1, -1), .4, LINE),
    ]
    for row_index in range(2, len(table_rows), 2):
        expense_style.append(("BACKGROUND", (0, row_index), (-1, row_index), PAPER))
    if len(table_rows) == 2 and not summary.get("expenses"):
        expense_style.append(("SPAN", (0, 1), (-1, 1)))
    expense_table.setStyle(TableStyle(expense_style))
    story.extend([expense_table, Spacer(1, 6 * mm),
                  KeepTogether([Paragraph("About this report", section),
                                Paragraph("Amounts are based on expenses recorded in Aniro for the selected month. Unlinked expenses are included in spending totals but do not change a cash, bank, or e-wallet balance.", subtitle)])])

    def page(canvas, document):
        canvas.saveState()
        width, height = A4
        canvas.setFillColor(INK)
        canvas.setFont("Jakarta-ExtraBold", 15)
        canvas.drawString(18 * mm, height - 16 * mm, "Aniro")
        logo_width = pdfmetrics.stringWidth("Aniro", "Jakarta-ExtraBold", 15)
        canvas.setFillColor(GREEN)
        canvas.circle(18 * mm + logo_width + 3, height - 13.7 * mm, 2.2, fill=1, stroke=0)
        canvas.setFillColor(MUTED)
        canvas.setFont("Jakarta-Bold", 7)
        canvas.drawRightString(width - 18 * mm, height - 15 * mm, "MONEY REPORT")
        canvas.setStrokeColor(LINE)
        canvas.line(18 * mm, height - 21 * mm, width - 18 * mm, height - 21 * mm)
        canvas.setFont("Jakarta", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 10 * mm, "Private financial summary - generated by Aniro")
        canvas.drawRightString(width - 18 * mm, 10 * mm, f"Page {document.page}")
        canvas.restoreState()

    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="money-report")
    doc.addPageTemplates(PageTemplate(id="money-pages", frames=[frame], onPage=page))
    doc.build(story)
    return output.getvalue()
