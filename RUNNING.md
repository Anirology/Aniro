# Running Aniro through Stage 2

From the repository root, after one-time setup:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

Open http://127.0.0.1:5173/plan for weekly planning or http://127.0.0.1:5173/clarity for the goal hierarchy. The API runs on http://127.0.0.1:8000 and serves its OpenAPI documentation at `/docs`. The database is `backend/aniro.db`. `start.ps1` applies Alembic migrations and launches both local servers.

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

Stage 1 contains Clarity onboarding and goal hierarchy. Stage 2 adds weekly goals and linked tasks, editable calendar blocks, completion results, undo, capacity, and seasonal priority. Reflect and Money remain navigable with empty states for later stages. New databases contain no life areas, goals, modules, tasks, budget, or example records. The app creates only a local user row on the first API request.

Run the focused Stage 2 tests from `backend` with `& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -v`. The Stage 2 migration preserves existing Clarity records; a pre-migration SQLite backup is at `backend/aniro.pre-stage2.db` in this workspace.
