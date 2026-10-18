# Running Aniro through Stage 3

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

Stage 1 contains Clarity onboarding and goal hierarchy. Stage 2 adds weekly goals and linked tasks, editable calendar blocks, completion results, undo, capacity, and seasonal priority. Stage 3 adds explicit habit check-ins, 30-day streak/consistency, module progress calculated from Plan records, evidence-based coach prompts, user-set balance targets, monthly LKR budgets, expense categories and entries, JSON backup export, and expense CSV export. New databases contain no life areas, goals, modules, tasks, habits, budget, expenses, or example records. The app creates only a local user row on the first API request.

Run the focused tests from `backend` with `& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -v`. The migrations preserve existing Clarity and Plan records; local pre-migration SQLite backups are at `backend/aniro.pre-stage2.db` and `backend/aniro.pre-stage3.db` in this workspace. They are ignored by Git. Exports are available from Reflect and Money or at `/api/export/json` and `/api/export/expenses.csv`.
