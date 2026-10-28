# Aniro demo data and user-flow verification

Date: 28 October 2026  
Environment: local development database and live browser at `127.0.0.1`

## Outcome

All user-facing, demo-safe tables are populated. The full automated backend suite passes, the frontend production build succeeds, every main page renders populated content, and all live API smoke checks return HTTP 200. No critical defects were found.

## Safety and recovery

The running database used SQLite WAL mode, so the first raw file copy represented an older checkpoint rather than an exact pre-seed state. It has been preserved honestly as:

`backend/backups/aniro-legacy-checkpoint-20261023.db`

The closest earlier application snapshot remains:

`backend/backups/aniro-before-demo-money-20261028-022445.db`

After seeding, a verified, integrity-checked snapshot was created through SQLite's backup API:

`backend/backups/aniro-after-full-demo-20261028-114500.db`

The seeder is idempotent. Running it twice produced identical table counts and no duplicate demo records.

Google OAuth credentials, encrypted tokens, and internal backup snapshots were intentionally not populated. This prevents the demo from appearing connected to a real Google account or interfering with security and restore behavior.

## Populated table counts

| Table | Rows |
|---|---:|
| life_areas | 9 |
| tracks | 10 |
| modules | 12 |
| visions | 19 |
| recurring_weekly_goals | 7 |
| goals | 20 |
| weekly_plans | 3 |
| tasks | 60 |
| calendar_blocks | 48 |
| completion_logs | 13 |
| focus_preferences | 1 |
| focus_sessions | 7 |
| habits | 8 |
| habit_checkins | 39 |
| balance_targets | 8 |
| area_balance_targets | 8 |
| reflect_settings | 1 |
| budget_months | 2 |
| expense_categories | 7 |
| financial_accounts | 4 |
| expense_envelopes | 5 |
| upcoming_bills | 4 |
| expenses | 22 |
| coach_usage | 3 |

## Browser verification

| Page | Result | Populated evidence |
|---|---|---|
| Clarity | Pass | 10 visible demo-labelled records; areas, tracks, modules, and visions render |
| Plan | Pass | 12 visible demo-labelled records; current-week goals, tasks, blocks, and recurrence render |
| Study Flow | Pass | 8 visible demo-labelled tasks and 50 available task options; focus history is populated |
| Reflect | Pass | 52 visible demo-labelled records; habits, consistency, balance targets, goals, and completion data render |
| Money | Pass | 17 visible demo-labelled records; accounts, expenses, envelopes, bills, charts, and PDF export render |

The live browser console contained no errors or warnings during the final Money-page inspection.

## Automated user-flow coverage

All 36 backend tests passed. Coverage includes:

- Clarity hierarchy, vision relationships, horizon validation, archive safeguards, and goal ownership.
- Weekly planning, goal/task linking, quick capture, carry-over, batch review, scheduling conflicts, completion correction, daily recurrence, weekly recurrence, and stopping recurrence.
- Study Flow start, pause, breaks, two-minute return, task retention, work recording, unlinked sessions, and correcting an attempt.
- Reflect habits, check-ins, streaks, consistency, recorded minutes, target balance, and repeated-shortfall coaching prompts.
- Money budgets, categories, expenses, account balance updates, envelopes, safe-to-spend calculation, bills, graphs data, edit/delete behavior, and branded PDF output.
- JSON backup preview/restore, invalid-backup rejection, local pre-restore snapshot creation, recurring-data portability, and legacy backup compatibility.
- Google token encryption, refresh behavior, calendar create/edit/delete/disconnect, imported-event safeguards, and linked-block guards using isolated mocked Google responses.
- Coach privacy opt-in and fallback behavior without transmitting live user data.

## Live API smoke matrix

All of these returned HTTP 200:

- `/api/health`
- `/api/overview`
- `/api/plan?week=2026-10-26`
- `/api/focus`
- `/api/focus/tasks`
- `/api/focus/history`
- `/api/reflect?week=2026-10-26`
- `/api/money?month=2026-10`
- `/api/integrations/google/status`
- `/api/coach/status`
- `/api/export/expenses.pdf?month=2026-10`

The PDF endpoint returned `application/pdf` with a valid non-empty report.

## Build verification

- Backend: 36 tests passed in 27.7 seconds.
- Frontend: TypeScript compilation and Vite production build passed.
- Database migration: `0012_student_money_tools` is current.

## Limitations of this verification

Real Google Calendar authorization and real external coach requests were not performed. Doing so would require a live Google account and could transmit data or consume API quota. Their application logic is covered by isolated automated tests instead.

## Re-running the demo seeder

From the backend directory:

```powershell
.\.venv\Scripts\python.exe seed_demo.py
```

It is safe to run repeatedly; deterministic IDs and uniqueness checks prevent duplicate demo records.
