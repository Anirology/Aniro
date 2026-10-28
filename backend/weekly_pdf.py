"""Weekly review document, using the existing Aniro report typography."""
from datetime import date, timedelta
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable
from money_pdf import _register_fonts, _money, INK, MUTED, GREEN, LINE, PAPER, PALE_GREEN


def duration(value):
    hours, minutes = divmod(int(value or 0), 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


class TimeChart(Flowable):
    def __init__(self, width, planned, recorded, target):
        super().__init__()
        self.width, self.height = width, 112
        self.values = [('Planned', planned, colors.HexColor('#98ACA0')),
                       ('Recorded', recorded, GREEN), ('Track targets', target, INK)]

    def draw(self):
        maximum = max(1, *(v for _, v, _ in self.values))
        for index, (label, value, tone) in enumerate(self.values):
            y = 88-index*32
            self.canv.setFillColor(MUTED)
            self.canv.setFont('Jakarta-Bold',8)
            self.canv.drawString(0,y+10,label)
            self.canv.drawRightString(self.width,y+10,duration(value))
            self.canv.setFillColor(LINE)
            self.canv.roundRect(0,y-1,self.width,5,2.5,fill=1,stroke=0)
            if value:
                self.canv.setFillColor(tone)
                self.canv.roundRect(0,y-1,self.width*value/maximum,5,2.5,fill=1,stroke=0)


def build_weekly_pdf(summary, finance, display_name=""):
    _register_fonts()
    output = BytesIO()
    start = date.fromisoformat(summary['week'])
    end = start + timedelta(days=6)
    period = f"{start:%d %b} - {end:%d %b %Y}"
    doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm,
                            topMargin=29*mm, bottomMargin=20*mm,
                            title=f"Aniro weekly review - {period}", author=display_name or 'Aniro')
    body = ParagraphStyle('body', fontName='Jakarta', fontSize=8, leading=12, textColor=INK)
    muted = ParagraphStyle('muted', parent=body, textColor=MUTED)
    heading = ParagraphStyle('heading', parent=body, fontName='Jakarta-Bold', fontSize=12, leading=17, spaceBefore=16, spaceAfter=8, keepWithNext=True)
    title = ParagraphStyle('title', parent=heading, fontName='Jakarta-ExtraBold', fontSize=29, leading=34, spaceBefore=0)
    def p(value, style=body):
        return Paragraph(escape(str(value)), style)
    story = []
    def section(label):
        story.append(p(label, heading))
    def table(headers, rows, widths):
        values = [[p(v) for v in headers]] + [[p(v) for v in row] for row in rows]
        if not rows:
            values.append([p('No records for this period.')] + ['']*(len(headers)-1))
        result = Table(values, colWidths=[doc.width*w for w in widths], repeatRows=1, hAlign='LEFT')
        result.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),PALE_GREEN), ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PAPER]),
            ('VALIGN',(0,0),(-1,-1),'TOP'), ('LINEBELOW',(0,0),(-1,0),.7,LINE),
            ('LINEBELOW',(0,1),(-1,-1),.3,LINE), ('LEFTPADDING',(0,0),(-1,-1),9),
            ('RIGHTPADDING',(0,0),(-1,-1),9), ('TOPPADDING',(0,0),(-1,-1),9), ('BOTTOMPADDING',(0,0),(-1,-1),9)]))
        story.append(result)
    story.extend([p('Your week, in perspective.', title), p(period, heading),
                  p(f"{display_name or 'Personal'} / Weekly review and meeting brief", muted), Spacer(1,12)])
    totals = summary['totals']
    tracks = [b for b in summary['balance'] if b['scope']=='track']
    target = sum(b['target_minutes'] or 0 for b in tracks)
    section('01 / The week at a glance')
    table(['PLANNED','RECORDED','TRACK TARGETS','TASKS DONE'], [[duration(totals['planned_minutes']),duration(totals['completed_minutes']),duration(target),totals['completed_tasks']]], [.25]*4)
    story.extend([Spacer(1,20),TimeChart(doc.width,totals['planned_minutes'],totals['completed_minutes'],target)])
    achieved = sum(g['status']=='completed' for g in summary['goals'])
    section('Weekly outcomes')
    story.append(p(f"{achieved} of {len(summary['goals'])} weekly goals marked complete. "
                   f"{len(summary['focus_records'])} study attempts ended during this week."))
    story.append(p('Time and goal totals follow the selected weekly plan in Reflect. Targets and goal status are the values at export; historical target revisions are not stored. Study attempts use their local end date.', muted))
    section('Habits / seven-day check-in map')
    days = [start+timedelta(days=i) for i in range(7)]
    rows=[]
    for h in summary['habits']:
        if h['created_on']>end.isoformat():
            continue
        marks=[]
        for d in days:
            eligible=d.isoformat()>=h['created_on'] and d.isoformat()<=summary['today'] and (h['frequency_rule']!='weekdays' or d.weekday()<5)
            marks.append('Yes' if eligible and d.isoformat() in h['checked_dates'] else '-' if not eligible else 'No')
        rows.append([h['name'],*marks,f"{h['current_streak']} days"])
    table(['Habit',*[d.strftime('%a') for d in days],'Streak*'],rows,[.30,*([.08]*7),.14])
    story.append(p('* Streak measured at the report cutoff. Yes = checked; No = eligible but unchecked; - = not eligible or future.',muted))
    story.append(PageBreak())
    story.append(p('Progress & balance',title))
    section('02 / Weekly goals')
    table(['Goal / life area','Status','Tasks done','Planned','Recorded'],[[f"{g['title']} / {g['area_name']}",g['status'],f"{g['completed_tasks']}/{g['task_count']}",duration(g['planned_minutes']),duration(g['completed_minutes'])] for g in summary['goals']],[.40,.15,.13,.16,.16])
    section('03 / Life areas and track targets')
    for area in summary['areas']:
        ids={t['id'] for t in summary['tracks'] if t['life_area_id']==area['id']}
        children=[b for b in tracks if b['id'] in ids]
        if not children:
            continue
        actual=sum(b['completed_minutes'] for b in children)
        goal=sum(b['target_minutes'] or 0 for b in children)
        section(f"{area['name']} / {duration(actual)} recorded / {duration(goal)} target")
        table(['Track','Weekly target','Recorded','Target reached'],[[b['name'],duration(b['target_minutes']) if b['target_minutes'] is not None else 'Not set',duration(b['completed_minutes']),f"{b['completed_minutes']/b['target_minutes']:.0%}" if b['target_minutes'] else '-'] for b in children],[.40,.20,.20,.20])
    story.append(p('Category totals sum tracks only. Unassigned or area-only work remains included in the overall recorded total.',muted))
    section('Time by module')
    table(['Area / track / module','Planned','Recorded'],[[f"{r['area_name']} / {r['track_name']} / {r['module_name']}",duration(r['planned_minutes']),duration(r['completed_minutes'])] for r in summary['modules']],[.60,.20,.20])
    story.append(PageBreak())
    story.append(p('Money & next steps',title))
    section('04 / Weekly money dashboard')
    table(['WEEKLY SPENDING','WEEKLY INCOME','TRANSFERS'],[[_money(finance['spent']),_money(finance['income']),_money(finance['transfers'])]],[1/3]*3)
    story.append(p('Transfers move existing money between balances; they are excluded from income and spending.',muted))
    section('Spending by category')
    table(['Category','Spent this week'],finance['categories'],[.70,.30])
    section('Monthly budget context')
    table(['Month','Budget','Month spending','Budget remaining'],finance['months'],[.22,.26,.26,.26])
    story.append(p('Monthly figures cover each whole calendar month touched by the selected week. They are not weekly limits.',muted))
    section('Meeting notes')
    story.append(p('Discuss: What moved forward? Which target needs adjusting? What spending can wait until next week?',body))
    for prompt in summary['prompts']:
        story.append(p(prompt['text'],body))
        story.append(Spacer(1,7))
    for label in ['Keep doing','Change next week','One concrete next action']:
        section(label)
        story.append(Spacer(1,15))
    if summary['focus_records']:
        story.append(PageBreak())
        story.append(p('Study journal',title))
        story.append(p('Attempts ended during the selected week. These records explain the time above; do not add them again.',muted))
        section('05 / Attempts, learning and follow-ups')
        table(['Task / result','Focus','Notes and next action'],[[f"{r['task_title'] or 'Unlinked study'} / {r['status'] or 'Unrecorded'}",duration(r['recorded_minutes']),f"{r['note'] or 'No note'}\nNext: {r['next_action'] or 'Not specified'}\nLearning checked: {'Yes' if r['learning_checked'] else 'No'}; difficult: {'Yes' if r['difficulty'] else 'No'}"] for r in summary['focus_records']],[.30,.13,.57])
    def page(canvas, document):
        canvas.saveState()
        canvas.setFillColor(INK)
        canvas.setFont('Jakarta-ExtraBold',16)
        canvas.drawString(18*mm,A4[1]-16*mm,'Aniro')
        canvas.setFillColor(GREEN)
        canvas.circle(36*mm,A4[1]-14*mm,2,fill=1,stroke=0)
        canvas.setFillColor(MUTED)
        canvas.setFont('Jakarta',7)
        canvas.drawRightString(A4[0]-18*mm,A4[1]-15*mm,'WEEKLY REVIEW / '+period)
        canvas.setStrokeColor(LINE)
        canvas.line(18*mm,A4[1]-21*mm,A4[0]-18*mm,A4[1]-21*mm)
        canvas.drawString(18*mm,11*mm,'Private / Aniro weekly review')
        canvas.drawRightString(A4[0]-18*mm,11*mm,f'{document.page:02d}')
        canvas.restoreState()
    doc.build(story,onFirstPage=page,onLaterPages=page)
    return output.getvalue()
