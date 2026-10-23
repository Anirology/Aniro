# Running Aniro through Stage 4

From the repository root, after one-time setup:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

Open http://127.0.0.1:5173/reflect for habit and progress review, http://127.0.0.1:5173/money for budgeting, http://127.0.0.1:5173/plan for weekly goals, or http://127.0.0.1:5173/clarity for long-term visions. The API runs on http://127.0.0.1:8000 and serves its OpenAPI documentation at `/docs`. The database is `backend/aniro.db`. `start.ps1` applies Alembic migrations and launches both local servers.

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

Clarity stores long-term horizons in `visions`; Plan stores actionable weekly outcomes in `goals`, and tasks link only to weekly goals. A weekly goal can link to a longer vision. The migration moves existing long-term records into `visions`, preserving their IDs and links. Stage 2 adds linked tasks, editable calendar blocks, completion results, undo, capacity, and seasonal priority. Stage 3 adds explicit habit check-ins, 30-day streak/consistency, module progress calculated from Plan records, evidence-based coach prompts, user-set balance targets, monthly LKR budgets, expense categories and entries, JSON backup export, and expense CSV export. Stage 4 adds optional Google Calendar and Gemini integrations. New databases contain no life areas, visions, goals, modules, tasks, habits, budget, expenses, example records, or connected accounts. The app creates only a local user row on the first API request.

For a simple daily flow, open a life area in Clarity, add a vision, then choose **Add weekly goal** there. Plan opens the goal form with that life area selected. Add tasks under the goal and schedule Aniro blocks for the tasks. Record done or partial work in Plan. Reflect then shows the weekly goal beside its linked vision, task completion, scheduled block time, and recorded work. The separate area/track/module table groups the same task time by subject. Visions themselves have no time totals; Google events alone do not become completed work. Habits are separate daily check-ins.

Run the focused tests from `backend` with `& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -v`. The migrations preserve existing Clarity and Plan records; local pre-migration SQLite backups are at `backend/aniro.pre-stage2.db` and `backend/aniro.pre-stage3.db` in this workspace. They are ignored by Git. Exports are available from Reflect and Money or at `/api/export/json` and `/api/export/expenses.csv`.

Plan now opens with a Today view above the week calendar. It shows the next Aniro block, its weekly goal and linked vision, direct result actions, and earlier blocks that can be reviewed or moved. The root URL opens Plan. Reflect starts with a short weekly summary and links back to editing each weekly goal. Money can create a category together with its first expense.

The main return point is now **Resume** in Plan. It offers one current or unfinished block with one-tap Done/Skip, a Tomorrow action within the same week, and an optional batch review of unfinished blocks. **Capture** in the sidebar saves a one-line standalone task to the current local week from any page. Plan can explicitly carry an unfinished task from the previous week into the selected week; the original task and its history remain in place, while the new task starts unscheduled and can be linked to a new weekly goal. Weekly statistics, longer vision horizons, reflection detail, and money categories remain available behind expandable sections so the daily path stays short.

Reflect has **Restore JSON** next to Export backup. It previews an `aniro-json-v1` export and requires an explicit confirmation before replacing local records. The backend first saves a SQLite snapshot in `backend/backups/`. The restore runs in one database transaction and disconnects Google Calendar locally; reconnect it afterward. Keep both the JSON export and the automatic snapshot until you have checked the restored data.

## Connect aniruththens@gmail.com Google Calendar

1. In [Google Cloud Console](https://console.cloud.google.com/), create or select a project and [enable Google Calendar API](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com).
2. In **Google Auth Platform → Branding**, set the app name to `Aniro` and enter your contact email. In **Audience**, choose **External** for a personal Gmail account, start in **Testing**, and add `aniruththens@gmail.com` under **Test users**. For a lasting connection, change the app to **In production** in the Google Auth Platform Audience settings when you are ready, then reconnect once. Review Google's verification requirements before sharing the app with anyone else. In **Data Access**, add `openid`, `email`, `https://www.googleapis.com/auth/calendar.calendarlist.readonly`, and `https://www.googleapis.com/auth/calendar.events.owned`.
3. In **Google Auth Platform → Clients → Create client**, choose **Web application**. Add this **Authorized redirect URI exactly**: `http://127.0.0.1:8000/api/integrations/google/callback`. Copy the client ID and client secret.
4. Download the client's JSON and save it as `backend/google_oauth_client.json`. Run `& backend/.venv/Scripts/python.exe backend/configure_google.py` from the repository root to import it into the prepared `backend/.env` file. Keep these files on your computer; do not paste secrets into chat or commit them. Restart the backend after editing `.env`.
5. Open [Plan](http://127.0.0.1:5173/plan), choose **Connect Google**, sign in as `aniruththens@gmail.com`, approve access, and select your primary calendar. Plan shows a large week view loaded through Aniro's private Google API connection, with the weekly event list collapsed until opened. Click a time slot to create a Google event or an Aniro task block with adjustable start and end times. Google events can include a location, description, color, or all-day dates. New task blocks sync to Google by default when connected. Click an event to edit or delete it in Google; click an Aniro block to edit its task and time, which syncs on save. Calendar Booked counts overlapping busy time once across Google events and local blocks; Google events marked Free and all-day events do not consume booked hours. Room Left compares that time with your own Available Time setting. Actual Work counts only recorded task results. **Open Google Calendar** opens Google's native interface in a separate tab. **Weekly Goals** opens over the calendar. **Disconnect** keeps local records and leaves existing Google events in place.

The app requests only the calendar list and events on calendars you own, plus email to verify the specified account. It never requests full calendar-management permission. Google may show an unverified-app warning for a private testing project. In Google's Testing status, Calendar refresh authorization expires after seven days. Moving the OAuth app to **In production** and reconnecting avoids that testing limit; Google can still revoke tokens for other reasons. A temporary network failure should show a network error rather than asking you to reconnect. Google Calendar controls reminders. This local app listens on `127.0.0.1`, so it must be running when you connect.

If Calendar reports that the backend cannot reach Google, stop the API and run `start.ps1` from a normal PowerShell session with internet access. A restricted development shell can serve the local pages while blocking the API process's outbound Google requests.

## Optional Gemini coach

Create a key at [Google AI Studio API keys](https://aistudio.google.com/app/apikey), add `ANIRO_GEMINI_API_KEY=...` to `backend/.env`, and restart the API. The drawer works with local deterministic insights without a key. When configured, Aniru sends your message, recent chat, and basic progress counts to Gemini when you press **Send to Aniru**. Finance totals and goal/task titles have separate opt-ins; raw expenses and notes are never included. The chat drawer does not show a context preview or persist the conversation after it closes. There is a local limit of 10 Gemini requests per day. Tokens and API keys stay in the backend. Google OAuth tokens are encrypted in SQLite using a generated local `backend/.token_key`, which is ignored by Git; keep this file if you move or restore the database.
