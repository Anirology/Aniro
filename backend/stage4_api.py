"""Optional local integrations. Secrets and OAuth tokens never leave FastAPI."""
import base64
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from db import SessionLocal
from models import User, Goal, Task, CalendarBlock, CompletionLog, BudgetMonth, Expense, GoogleIntegration, CoachUsage
from plan_api import current_user, owner_block, encoded, week_date

router = APIRouter(prefix="/api")
ROOT = Path(__file__).resolve().parent
FRONTEND = "http://127.0.0.1:5173"
GOOGLE_SCOPES = (
    "openid", "email",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/calendar.events.owned",
)
PROMPT_VERSION = "prd-v1"
SYSTEM_PROMPT = """You are Abdaal, Aniro's concise AI productivity coach. You are an original assistant inspired by friendly, practical, reflective productivity principles. Do not claim to be Ali Abdaal, imitate his exact wording, or imply his endorsement.

Help the user turn long-term goals into realistic weekly action, review planned versus completed work, and reason about an LKR personal budget. Be warm, direct, and occasionally challenging without insult or shame. Lead with the answer. Use at most 80 words unless the user explicitly asks for depth. Prefer 1-3 short bullets and at most one useful follow-up question. Avoid slogans and generic praise.

Use only the structured Aniro context supplied with this request. Distinguish facts, missing data, and suggestions. Never invent a completed task, balance, deadline, or relationship detail. Do not diagnose the user or predict grades, career outcomes, investment returns, or exchange rates. For money questions, provide budgeting arithmetic and options; do not present speculative financial advice as certain.

Never modify app records. If a change would help, suggest it and wait for the user to use a visible confirmation control. If context is missing, ask one concise clarifying question. If Gemini is unavailable, the app should show a deterministic insight instead."""

def session():
    with SessionLocal() as db: yield db

def setting(name: str) -> str:
    if name in os.environ: return os.environ[name].strip()
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip().startswith(name + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""

def redirect_uri(): return setting("ANIRO_GOOGLE_REDIRECT_URI") or "http://127.0.0.1:8000/api/integrations/google/callback"
def configured(): return bool(setting("ANIRO_GOOGLE_CLIENT_ID") and setting("ANIRO_GOOGLE_CLIENT_SECRET"))

def _token_key() -> str:
    key = setting("ANIRO_TOKEN_KEY")
    if key: return key
    path = ROOT / ".token_key"
    if not path.exists():
        # Exclusive create; never replace a key that already encrypted tokens.
        try:
            with path.open("x", encoding="ascii") as file:
                file.write(base64.b64encode(secrets.token_bytes(32)).decode())
        except FileExistsError: pass
    return path.read_text(encoding="ascii").strip()

def _crypto(mode: str, payload: str) -> str:
    if os.name != "nt": raise RuntimeError("This local token store requires Windows")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "token_crypto.ps1")],
                            input=json.dumps({"mode": mode, "key": _token_key(), "payload": payload}),
                            text=True, capture_output=True, timeout=15)
    if result.returncode or not result.stdout: raise RuntimeError("Could not protect the Google token")
    return result.stdout

def protect(data: dict) -> str:
    return _crypto("encrypt", json.dumps(data))

def unprotect(value: str) -> dict:
    return json.loads(_crypto("decrypt", value))

class RemoteError(Exception):
    def __init__(self, status: int, detail: str): self.status, self.detail = status, detail

def http_json(method: str, url: str, *, data: dict | None = None, form: bool = False, token: str | None = None, key: str | None = None) -> dict:
    headers = {"Accept": "application/json"}
    if token: headers["Authorization"] = "Bearer " + token
    if key: headers["x-goog-api-key"] = key
    body = None
    if data is not None:
        body = urlencode(data).encode() if form else json.dumps(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=12) as response:
            content = response.read()
            return json.loads(content) if content else {}
    except HTTPError as error:
        raise RemoteError(error.code, f"Provider returned HTTP {error.code}") from error
    except (URLError, TimeoutError) as error:
        raise RemoteError(503, "Provider is unreachable") from error

def integration(db: Session, create=False):
    uid = current_user(db).id
    record = db.get(GoogleIntegration, uid)
    if not record and create:
        record = GoogleIntegration(user_id=uid)
        db.add(record)
        db.flush()
    return record

def google_status(db: Session):
    record = integration(db)
    return {"configured": configured(), "connected": bool(record and record.encrypted_token),
            "expected_email": setting("ANIRO_GOOGLE_ALLOWED_EMAIL") or None,
            "account_email": record.account_email if record and record.encrypted_token else None,
            "selected_calendar_id": record.selected_calendar_id if record and record.encrypted_token else None,
            "last_error": record.last_error if record else None,
            "scopes": list(GOOGLE_SCOPES)}

@router.get("/integrations/google/status")
def status(db: Session = Depends(session)):
    return google_status(db)

@router.get("/integrations/google/start")
def google_start(db: Session = Depends(session)):
    if not configured(): raise HTTPException(503, "Add Google OAuth client ID and secret to backend/.env, then restart the API")
    record = integration(db, True)
    record.oauth_state = secrets.token_urlsafe(32)
    record.code_verifier = secrets.token_urlsafe(64)
    record.oauth_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=10)
    record.last_error = None
    db.commit()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(record.code_verifier.encode()).digest()).rstrip(b"=").decode()
    params = {"client_id": setting("ANIRO_GOOGLE_CLIENT_ID"), "redirect_uri": redirect_uri(), "response_type": "code",
              "scope": " ".join(GOOGLE_SCOPES), "access_type": "offline", "prompt": "consent select_account",
              "state": record.oauth_state, "code_challenge": challenge, "code_challenge_method": "S256"}
    return RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))

@router.get("/integrations/google/callback")
def google_callback(state: str = "", code: str = "", error: str = "", db: Session = Depends(session)):
    record = integration(db)
    if not record or not state or not secrets.compare_digest(state, record.oauth_state or "") or not record.oauth_expires_at or record.oauth_expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(400, "Google connection expired or state did not match. Start again from Plan.")
    verifier = record.code_verifier
    record.oauth_state = record.code_verifier = None
    record.oauth_expires_at = None
    db.commit()
    if error or not code: return RedirectResponse(FRONTEND + "/plan?google=denied")
    try:
        token = http_json("POST", "https://oauth2.googleapis.com/token", data={
            "client_id": setting("ANIRO_GOOGLE_CLIENT_ID"), "client_secret": setting("ANIRO_GOOGLE_CLIENT_SECRET"),
            "code": code, "code_verifier": verifier, "redirect_uri": redirect_uri(), "grant_type": "authorization_code"}, form=True)
        token["created_at"] = datetime.now(timezone.utc).timestamp()
        account = http_json("GET", "https://openidconnect.googleapis.com/v1/userinfo", token=token["access_token"])
        email = account.get("email", "")
        if not email or not account.get("email_verified"):
            raise RemoteError(403, "Google account email was not verified")
        allowed = setting("ANIRO_GOOGLE_ALLOWED_EMAIL")
        if allowed and email.lower() != allowed.lower():
            raise RemoteError(403, "Connected Google account is not the configured account")
        if record.account_email and record.account_email.lower() != email.lower() and db.scalar(select(CalendarBlock.id).where(CalendarBlock.google_event_id.is_not(None)).limit(1)):
            raise RemoteError(409, "Disconnect the existing account before connecting another")
        previous_calendar = record.selected_calendar_id if record.account_email and record.account_email.lower() == email.lower() else None
        if previous_calendar and not token.get("refresh_token") and record.encrypted_token:
            token["refresh_token"] = unprotect(record.encrypted_token).get("refresh_token")
        record.account_email = email
        record.encrypted_token = protect(token)
        record.selected_calendar_id = previous_calendar
        record.last_error = None
        db.commit()
        return RedirectResponse(FRONTEND + "/plan?google=connected")
    except (RemoteError, KeyError, RuntimeError) as exc:
        record.last_error = "Google connection failed. Retry from Plan."
        db.commit()
        return RedirectResponse(FRONTEND + "/plan?google=error")

def access_token(db: Session, record: GoogleIntegration) -> str:
    if not record.encrypted_token: raise HTTPException(409, "Connect Google Calendar first")
    try: token = unprotect(record.encrypted_token)
    except Exception:
        record.last_error = "Stored Google token is unavailable for this Windows user. Reconnect."
        db.commit()
        raise HTTPException(409, record.last_error)
    expires_at = token.get("created_at", 0) + token.get("expires_in", 0)
    if expires_at > datetime.now(timezone.utc).timestamp() + 60: return token["access_token"]
    if not token.get("refresh_token"):
        record.last_error = "Google authorization expired. Reconnect."
        db.commit()
        raise HTTPException(409, record.last_error)
    try:
        fresh = http_json("POST", "https://oauth2.googleapis.com/token", data={
            "client_id": setting("ANIRO_GOOGLE_CLIENT_ID"), "client_secret": setting("ANIRO_GOOGLE_CLIENT_SECRET"),
            "refresh_token": token["refresh_token"], "grant_type": "refresh_token"}, form=True)
        token.update(fresh)
        token["created_at"] = datetime.now(timezone.utc).timestamp()
        record.encrypted_token = protect(token)
        record.last_error = None
        db.commit()
        return token["access_token"]
    except RemoteError:
        record.last_error = "Google authorization needs reconnection."
        db.commit()
        raise HTTPException(409, record.last_error)

def google_call(db: Session, method: str, path: str, data: dict | None = None, params: dict | None = None):
    record = integration(db)
    if not record: raise HTTPException(409, "Connect Google Calendar first")
    url = "https://www.googleapis.com/calendar/v3" + path + (("?" + urlencode(params)) if params else "")
    try:
        result = http_json(method, url, data=data, token=access_token(db, record))
        record.last_error = None
        db.commit()
        return result
    except RemoteError as exc:
        record.last_error = "Google Calendar could not sync (HTTP %s). %s" % (exc.status, "Reconnect if authorization changed." if exc.status in (401, 403) else "Try again later.")
        db.commit()
        raise HTTPException(502, record.last_error)

@router.get("/integrations/google/calendars")
def calendars(db: Session = Depends(session)):
    result = google_call(db, "GET", "/users/me/calendarList", params={"minAccessRole": "owner", "maxResults": 250})
    return {"calendars": [{"id": item["id"], "name": item.get("summary", item["id"]), "primary": item.get("primary", False)} for item in result.get("items", [])]}

@router.get("/integrations/google/colors")
def calendar_colors(db: Session = Depends(session)):
    return google_call(db, "GET", "/colors")

class CalendarChoice(BaseModel):
    calendar_id: str = Field(min_length=1, max_length=240)

@router.put("/integrations/google/calendar")
def choose_calendar(data: CalendarChoice, db: Session = Depends(session)):
    items = calendars(db)["calendars"]
    if data.calendar_id not in [item["id"] for item in items]: raise HTTPException(422, "Choose an owned calendar from the list")
    record = integration(db)
    if record.selected_calendar_id and record.selected_calendar_id != data.calendar_id:
        linked = db.scalar(select(CalendarBlock.id).where(CalendarBlock.google_event_id.is_not(None)).limit(1))
        if linked: raise HTTPException(409, "Remove or disconnect existing synced blocks before switching calendars")
    record.selected_calendar_id = data.calendar_id
    db.commit()
    return google_status(db)

def selected(db: Session):
    record = integration(db)
    if not record or not record.encrypted_token or not record.selected_calendar_id:
        raise HTTPException(409, "Connect Google and select a calendar first")
    return record.selected_calendar_id

@router.get("/integrations/google/events")
def events(week: str, db: Session = Depends(session)):
    start = week_date(week)
    calendar_id = selected(db)
    zone = ZoneInfo(current_user(db).timezone)
    results = []
    page = None
    for _ in range(10):
        params = {"timeMin": datetime.combine(start, datetime.min.time(), zone).isoformat(),
                  "timeMax": datetime.combine(start + timedelta(days=7), datetime.min.time(), zone).isoformat(),
                  "singleEvents": "true", "orderBy": "startTime", "maxResults": 250}
        if page: params["pageToken"] = page
        response = google_call(db, "GET", "/calendars/" + quote(calendar_id, safe="") + "/events", params=params)
        for event in response.get("items", []):
            results.append({"id": event.get("id"), "title": event.get("summary", "Busy"),
                            "start": event.get("start", {}).get("dateTime") or event.get("start", {}).get("date"),
                            "end": event.get("end", {}).get("dateTime") or event.get("end", {}).get("date"),
                            "all_day": "date" in event.get("start", {}), "link": event.get("htmlLink"),
                            "color_id": event.get("colorId"), "description": event.get("description", ""),
                            "location": event.get("location", ""), "busy": event.get("transparency") != "transparent",
                            "editable": event.get("creator", {}).get("self", False) or event.get("organizer", {}).get("self", False)})
        page = response.get("nextPageToken")
        if not page: break
    return {"events": results, "calendar_id": calendar_id}

class Confirm(BaseModel):
    confirm: bool


class CalendarEventIn(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    start: datetime | None = None
    end: datetime | None = None
    all_day: bool = False
    start_date: date | None = None
    end_date: date | None = None
    description: str = Field(default="", max_length=2000)
    location: str = Field(default="", max_length=500)
    color_id: str | None = Field(default=None, pattern=r"^[1-9][0-9]?$|^$")
    request_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")


def direct_event_body(data: CalendarEventIn):
    if data.all_day:
        if not data.start_date or not data.end_date or data.end_date <= data.start_date:
            raise HTTPException(422, "Choose valid all-day dates")
        start, end = {"date": data.start_date.isoformat()}, {"date": data.end_date.isoformat()}
    else:
        if not data.start or not data.end or data.start.tzinfo is None or data.end.tzinfo is None or data.end <= data.start:
            raise HTTPException(422, "Choose a valid start and end time")
        start, end = {"dateTime": data.start.isoformat()}, {"dateTime": data.end.isoformat()}
    body = {"summary": data.title.strip(), "start": start, "end": end,
            "description": data.description, "location": data.location}
    if not body["summary"]: raise HTTPException(422, "Event title is required")
    if data.color_id is not None: body["colorId"] = data.color_id or None
    return body


def direct_event_path(db: Session, event_id: str = ""):
    path = "/calendars/" + quote(selected(db), safe="") + "/events"
    if event_id:
        linked = db.scalar(select(CalendarBlock.id).where(CalendarBlock.google_event_id == event_id).limit(1))
        if linked: raise HTTPException(409, "Edit this synced event through its Aniro block")
        path += "/" + quote(event_id, safe="")
    return path


@router.post("/integrations/google/events", status_code=201)
def create_calendar_event(data: CalendarEventIn, db: Session = Depends(session)):
    body = direct_event_body(data)
    if not data.request_id: raise HTTPException(422, "Event request ID is required")
    body["id"] = "aniroevent" + data.request_id
    path = direct_event_path(db)
    try: return google_call(db, "POST", path, body, {"sendUpdates": "none"})
    except HTTPException as exc:
        if "HTTP 409" not in str(exc.detail): raise
        return google_call(db, "GET", path + "/" + body["id"])


@router.put("/integrations/google/events/{event_id}")
def update_calendar_event(event_id: str, data: CalendarEventIn, db: Session = Depends(session)):
    path = direct_event_path(db, event_id)
    body = direct_event_body(data)
    return google_call(db, "PATCH", path, body, {"sendUpdates": "none"})


@router.delete("/integrations/google/events/{event_id}")
def delete_calendar_event(event_id: str, confirm: bool = Query(False), db: Session = Depends(session)):
    if not confirm: raise HTTPException(400, "Confirm deletion from Google Calendar")
    path = direct_event_path(db, event_id)
    google_call(db, "DELETE", path, params={"sendUpdates": "none"})
    return {"deleted": True}

def event_body(db: Session, block: CalendarBlock):
    task = db.get(Task, block.task_id)
    return {"summary": task.title, "start": {"dateTime": block.start_at.replace(tzinfo=timezone.utc).isoformat()},
            "end": {"dateTime": block.end_at.replace(tzinfo=timezone.utc).isoformat()},
            "extendedProperties": {"private": {"aniroBlockId": block.id}}}

@router.post("/integrations/google/blocks/{id}/sync")
def sync_block(id: str, data: Confirm, db: Session = Depends(session)):
    if not data.confirm: raise HTTPException(400, "Confirm the Google Calendar write")
    calendar_id = selected(db)
    block = owner_block(db, id)
    if block.archived_at: raise HTTPException(409, "Restore the block before syncing")
    path = "/calendars/" + quote(calendar_id, safe="") + "/events"
    body = event_body(db, block)
    if block.google_event_id:
        result = google_call(db, "PUT", path + "/" + quote(block.google_event_id, safe=""), body)
    else:
        # A stable Google ID makes retries safe if the insert succeeds before local commit.
        event_id = "aniro" + block.id.replace("-", "")
        try: result = google_call(db, "POST", path, {**body, "id": event_id}, {"sendUpdates": "none"})
        except HTTPException as exc:
            if "HTTP 409" not in str(exc.detail): raise
            result = google_call(db, "GET", path + "/" + event_id)
            if result.get("extendedProperties", {}).get("private", {}).get("aniroBlockId") != block.id:
                raise HTTPException(409, "Google event ID collision; no event was linked")
        block.google_event_id = result["id"]
    block.sync_state = "synced"
    db.commit()
    return {"block": encoded(block), "google_event_id": block.google_event_id}

@router.post("/integrations/google/blocks/{id}/remove")
def remove_synced_block(id: str, data: Confirm, db: Session = Depends(session)):
    if not data.confirm: raise HTTPException(400, "Confirm removal from Google Calendar")
    calendar_id = selected(db)
    block = owner_block(db, id)
    if not block.google_event_id: raise HTTPException(409, "Block is not synced")
    path = "/calendars/" + quote(calendar_id, safe="") + "/events/" + quote(block.google_event_id, safe="")
    try: google_call(db, "DELETE", path, params={"sendUpdates": "none"})
    except HTTPException as exc:
        if "HTTP 404" not in str(exc.detail) and "HTTP 410" not in str(exc.detail): raise
    block.google_event_id = None
    block.sync_state = "local"
    block.archived_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return {"block": encoded(block), "google_deleted": True}

@router.post("/integrations/google/disconnect")
def disconnect(data: Confirm, db: Session = Depends(session)):
    if not data.confirm: raise HTTPException(400, "Confirm disconnect")
    record = integration(db)
    if record:
        record.encrypted_token = None
        record.selected_calendar_id = None
        record.account_email = None
        record.last_error = None
        record.oauth_state = record.code_verifier = None
        for block in db.scalars(select(CalendarBlock).where(CalendarBlock.google_event_id.is_not(None))):
            block.google_event_id = None
            block.sync_state = "disconnected"
        db.commit()
    return google_status(db)

def coach_context(db: Session, week: str, page: str, include_finance: bool, include_plan_titles: bool = False):
    uid = current_user(db).id
    tasks = list(db.scalars(select(Task).where(Task.user_id == uid, Task.week_start == week, Task.archived_at.is_(None))))
    ids = [task.id for task in tasks]
    blocks = list(db.scalars(select(CalendarBlock).where(CalendarBlock.task_id.in_(ids), CalendarBlock.archived_at.is_(None)))) if ids else []
    logs = list(db.scalars(select(CompletionLog).where(CompletionLog.task_id.in_(ids)))) if ids else []
    # Titles and notes stay local. Only aggregate counts and minutes go to Gemini by default.
    packet = {"page": page, "week": week, "task_count": len(tasks),
              "completed_task_count": sum(t.status == "done" for t in tasks),
              "planned_minutes": sum(round((b.end_at - b.start_at).total_seconds() / 60) for b in blocks),
              "completed_minutes": sum(log.completed_minutes for log in logs if log.result in ("done", "partial")),
              "weekly_goal_count": db.scalar(select(func.count(Goal.id)).where(Goal.user_id == uid, Goal.horizon == "week", Goal.target_date == week)) or 0}
    if include_plan_titles:
        goals = list(db.scalars(select(Goal).where(Goal.user_id == uid, Goal.horizon == "week", Goal.target_date == week, Goal.archived_at.is_(None)).limit(5)))
        packet["selected_goal_titles"] = [goal.title for goal in goals]
        packet["selected_task_titles"] = [task.title for task in tasks[:5]]
    if include_finance:
        month = week[:7]
        budget = db.scalar(select(BudgetMonth).where(BudgetMonth.user_id == uid, BudgetMonth.year == int(month[:4]), BudgetMonth.month == int(month[5:7])))
        if budget:
            spent = db.scalar(select(func.sum(Expense.amount_minor)).where(Expense.budget_month_id == budget.id)) or 0
            packet["finance_lkr"] = {"month": month, "budget": budget.limit_minor / 100, "spent": spent / 100, "remaining": (budget.limit_minor - spent) / 100}
    return packet

def deterministic(context: dict, question: str):
    if any(word in question.lower() for word in ("money", "budget", "spend", "expense", "lkr")):
        finance = context.get("finance_lkr")
        if finance: return f"Your {finance['month']} budget has LKR {finance['remaining']:,.2f} remaining. Review Money before adding a new expense."
        return "Open Money to set a monthly LKR budget. I can compare totals here when you allow finance context."
    if context["task_count"] == 0: return "This week has no tasks yet. Choose one weekly goal, then add a small task you can schedule."
    if context["completed_task_count"] == context["task_count"]: return "All this week’s tasks are marked done. Review Reflect, then choose one realistic next step."
    return f"You planned {context['planned_minutes']} minutes and recorded {context['completed_minutes']} completed minutes this week. Choose one remaining task and give it a realistic time block."

class CoachIn(BaseModel):
    question: str = Field(min_length=1, max_length=600)
    week: str
    page: str = Field(default="plan", pattern="^(clarity|plan|reflect|money)$")
    use_gemini: bool = False
    include_finance: bool = False
    include_plan_titles: bool = False

@router.post("/coach/context")
def preview(data: CoachIn, db: Session = Depends(session)):
    week_date(data.week)
    return {"context": coach_context(db, data.week, data.page, data.include_finance, data.include_plan_titles),
            "note": "Your question is also sent if you choose Gemini. Remove personal details before sending."}

@router.post("/coach/ask")
def ask(data: CoachIn, db: Session = Depends(session)):
    week_date(data.week)
    packet = coach_context(db, data.week, data.page, data.include_finance, data.include_plan_titles)
    fallback = deterministic(packet, data.question)
    key = setting("ANIRO_GEMINI_API_KEY")
    if not data.use_gemini or not key:
        return {"answer": fallback, "source": "local", "reason": "Gemini is not enabled or its key is missing", "context": packet}
    usage = db.get(CoachUsage, (current_user(db).id, date.today().isoformat()))
    if not usage:
        usage = CoachUsage(user_id=current_user(db).id, day=date.today().isoformat(), request_count=0, output_tokens=0)
        db.add(usage)
    if usage.request_count >= 10:
        return {"answer": fallback, "source": "local", "reason": "Daily AI limit reached", "context": packet}
    usage.request_count += 1
    db.commit()
    model = setting("ANIRO_GEMINI_MODEL") or "gemini-3.8-flash"
    payload = {"systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
               "contents": [{"role": "user", "parts": [{"text": json.dumps({"question": data.question, "context": packet})}]}],
               "generationConfig": {"maxOutputTokens": 180, "temperature": 0.4}}
    try:
        result = http_json("POST", f"https://generativelanguage.googleapis.com/v1beta/models/{quote(model, safe='')}:generateContent", data=payload, key=key)
        answer = " ".join(part.get("text", "") for candidate in result.get("candidates", [])[:1] for part in candidate.get("content", {}).get("parts", []))
        if not answer.strip(): raise RemoteError(502, "Empty AI response")
        if any(claim in answer.lower() for claim in ("i am ali abdaal", "i'm ali abdaal", "ali abdaal here", "as ali abdaal")):
            raise RemoteError(502, "Identity claim rejected")
        words = answer.split()
        if len(words) > 80: answer = " ".join(words[:80]) + "…"
        usage.output_tokens += result.get("usageMetadata", {}).get("candidatesTokenCount", 0)
        db.commit()
        return {"answer": answer, "source": "gemini", "context": packet}
    except (RemoteError, KeyError, ValueError):
        return {"answer": fallback, "source": "local", "reason": "Gemini is unavailable; showing a local insight", "context": packet}

@router.get("/coach/status")
def coach_status(): return {"gemini_configured": bool(setting("ANIRO_GEMINI_API_KEY")), "prompt_version": PROMPT_VERSION, "daily_limit": 10}
