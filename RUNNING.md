# Running Aniro through Stage 4

From the repository root, after one-time setup:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

Open http://127.0.0.1:5173/reflect for habit and progress review, http://127.0.0.1:5173/money for budgeting, http://127.0.0.1:5173/plan for weekly planning, or http://127.0.0.1:5173/clarity for the goal hierarchy. The API runs on http://127.0.0.1:8000 and serves its OpenAPI documentation at `/docs`. The database is `backend/aniro.db`. `start.ps1` applies Alembic migrations and launches both local servers.

One-time setup, with Python 3.11+ and Node.js 20+ installed:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd ..\frontend
npm.cmd install
cd ..
```

This workspace used `B:\CICADA\python.exe` for the first setup because `python` is not on PATH. The virtual environment is local to `backend`.

Stage 1 contains Clarity onboarding and goal hierarchy. Stage 2 adds weekly goals and linked tasks, editable calendar blocks, completion results, undo, capacity, and seasonal priority. Stage 3 adds explicit habit check-ins, 30-day streak/consistency, module progress calculated from Plan records, evidence-based coach prompts, user-set balance targets, monthly LKR budgets, expense categories and entries, JSON backup export, and expense CSV export. Stage 4 adds optional Google Calendar and Gemini integrations. New databases contain no life areas, goals, modules, tasks, habits, budget, expenses, example records, or connected accounts. The app creates only a local user row on the first API request.

Run the focused tests from `backend` with `& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -v`. The migrations preserve existing Clarity and Plan records; local pre-migration SQLite backups are at `backend/aniro.pre-stage2.db` and `backend/aniro.pre-stage3.db` in this workspace. They are ignored by Git. Exports are available from Reflect and Money or at `/api/export/json` and `/api/export/expenses.csv`.

## Connect aniruththens@gmail.com Google Calendar

1. In [Google Cloud Console](https://console.cloud.google.com/), create or select a project and [enable Google Calendar API](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com).
2. In **Google Auth Platform → Branding**, set the app name to `Aniro` and enter your contact email. In **Audience**, choose **External** for a personal Gmail account, leave it in **Testing**, and add `aniruththens@gmail.com` under **Test users**. In **Data Access**, add `openid`, `email`, `https://www.googleapis.com/auth/calendar.calendarlist.readonly`, and `https://www.googleapis.com/auth/calendar.events.owned`.
3. In **Google Auth Platform → Clients → Create client**, choose **Web application**. Add this **Authorized redirect URI exactly**: `http://127.0.0.1:8000/api/integrations/google/callback`. Copy the client ID and client secret.
4. Download the client's JSON and save it as `backend/google_oauth_client.json`. Run `& backend/.venv/Scripts/python.exe backend/configure_google.py` from the repository root to import it into the prepared `backend/.env` file. Keep these files on your computer; do not paste secrets into chat or commit them. Restart the backend after editing `.env`.
5. Open [Plan](http://127.0.0.1:5173/plan), choose **Connect Google**, sign in as `aniruththens@gmail.com`, approve access, and select your primary calendar. Plan shows a large week view loaded through Aniro's private Google API connection, with the weekly event list collapsed until opened. Click a time slot to create a Google event or an Aniro task block with adjustable start and end times. Google events can include a location, description, color, or all-day dates. New task blocks sync to Google by default when connected. Click an event to edit or delete it in Google; click an Aniro block to edit its task and time, which syncs on save. Calendar Booked counts overlapping busy time once across Google events and local blocks; Google events marked Free and all-day events do not consume booked hours. Room Left compares that time with your own Available Time setting. Actual Work counts only recorded task results. **Open Google Calendar** opens Google's native interface in a separate tab. **Weekly Goals** opens over the calendar. **Disconnect** keeps local records and leaves existing Google events in place.

The app requests only the calendar list and events on calendars you own, plus email to verify the specified account. It never requests full calendar-management permission. Google may show an unverified-app warning for a private testing project. In Google's Testing status, Calendar refresh authorization typically expires after seven days; use **Connect Google** again when needed. Google Calendar controls reminders. This local app listens on `127.0.0.1`, so it must be running when you connect.

## Optional Gemini coach

Create a key at [Google AI Studio API keys](https://aistudio.google.com/app/apikey), add `ANIRO_GEMINI_API_KEY=...` to `backend/.env`, and restart the API. The drawer works with local deterministic insights without a key. Gemini is used only when you tick **Send my question and previewed context to Gemini**. Finance totals and goal/task titles have separate opt-ins; raw expenses and notes are never included. The preview shows the exact structured app data; your typed question is also sent. There is a local limit of 10 Gemini requests per day. Tokens and API keys stay in the backend. Google OAuth tokens are encrypted in SQLite using a generated local `backend/.token_key`, which is ignored by Git; keep this file if you move or restore the database.
