# Aniro — five-stage build and review plan

**Companion document:** [Aniro PRD](Aniro-PRD.md)  
**Working rule:** One stage per work session. Target **3–4 hours of implementation plus up to 1 hour of testing and your review** inside a five-hour window. These are targets, not a guarantee; OAuth and external hosting can take longer because third-party setup is outside the codebase.

**Definition of “done” for every stage:** the app starts locally, a browser preview is available, the listed interactions work with persisted data, and the builder gives you a short handoff: what changed, exact start command/URL, test results, known gaps, and what you should inspect. Stop after that stage; incorporate your feedback before starting the next one. Do not mark a stage complete from screenshots alone.

## Stage 1 — runnable foundation and Clarity (target 3–4 hours)

**Build:** React + TypeScript + Vite frontend; FastAPI + SQLAlchemy + Alembic + SQLite backend; local start scripts; design tokens, Plus Jakarta Sans, Phosphor icons; responsive vertical navigation; all four page routes with honest empty states; fresh onboarding; Clarity life-area/track/module CRUD and editable horizon goals. No sample personal records. The user can create `Education → BIT → a module` and a 10-year goal, refresh, and see them persist.

**Review in browser:**

- [ ] App opens from a local URL with one clear start command.
- [ ] Clarity, Plan, Reflect, Money navigation works; other pages show useful empty states.
- [ ] Add, rename, archive, and restore a life area, track, and module.
- [ ] Add/edit a goal at two horizons; each horizon shows the actual area-specific goal text.
- [ ] The “This week → Plan” card opens Plan; weekly goals do not appear in Clarity.
- [ ] Refresh/restart preserves records; zero sample data appears on a fresh database.
- [ ] Narrow screen and keyboard navigation are usable.

**Prompt to attach with the PRD:**

> Implement **Stage 1 only** of `Aniro-Build-Stages.md` using the attached `Aniro-PRD.md` as the source of truth. Build a local React/TypeScript/Vite + FastAPI/SQLAlchemy/Alembic + SQLite app. Make the four routes browser-visible immediately, but implement full interactions only for onboarding and Clarity in this stage. Start with an empty database; do not seed the screenshot’s example records. Implement CRUD for life areas, tracks, modules, and horizon goals, with archive/restore when records are referenced. Match the PRD tokens and final screenshot direction. Run the app, verify the Stage 1 checklist, provide the local URL and exact start command, then stop for my review. Do not proceed to Stage 2.

## Stage 2 — weekly planning and completion (target 3–4 hours)

**Build:** weekly goals, tasks, breadcrumb paths, seven-day calendar, time blocks, user-defined colors, planned/done/partial/missed/moved states, completed-to-gray animation with undo, weekly available-time summary. Data persists through FastAPI and SQLite. No Google sync yet.

**Review in browser:**

- [ ] Create a goal linked to `Education → BIT → [module]` and see the breadcrumb in Plan.
- [ ] Add a task and schedule one or more blocks; calendar and sidebar show matching color/category.
- [ ] Mark done: task moves under Completed, grays out, retains category badge; undo works.
- [ ] Mark partial/missed/moved and record actual minutes; planned time never counts as completed time.
- [ ] Edit/reorder/archive tasks and reschedule blocks; reload preserves changes.
- [ ] Avoid scheduling overlaps or at least warn before saving them.

**Prompt to attach with the PRD:**

> Continue the existing Aniro project. Implement **Stage 2 only** from `Aniro-Build-Stages.md`, following the attached `Aniro-PRD.md` and preserving all Stage 1 data and behavior. Build the weekly Plan page with goal breadcrumbs, editable tasks and calendar blocks, all completion states, a smooth gray Completed transition, and undo. Persist everything through FastAPI/SQLite. Add only focused tests for goal-to-task linking and completion totals. Run and inspect the app in a browser, give me the preview URL/start command and checklist results, then stop for review. Do not start Google Calendar or Stage 3.

## Stage 3 — Reflect, Money, and export (target 3–4 hours)

**Build:** editable habits and check-ins; category-colored streak heatmap; 30-day consistency; module-level planned-versus-completed aggregates based on actual completion records; deterministic coach prompts and action links; monthly LKR budget, editable categories, expense CRUD, remaining/overspend calculations; JSON backup/export and CSV expense export. No Gemini yet.

**Review in browser:**

- [ ] BIT is blue, Design purple, YouTube red, Health orange, Relationships pink in streaks and charts.
- [ ] Add, edit, archive a habit and record/check/uncheck a day; streak updates correctly.
- [ ] Reflect can drill from BIT to module; planned and actual minutes match Stage 2 records.
- [ ] Coach prompt cites a real pattern; no invented completion or judgment from one miss.
- [ ] Enter LKR budget and expenses; amounts, percentages, remaining, and over-budget state recalculate after edits.
- [ ] Export data; inspect downloaded JSON/CSV; restart and confirm records remain.

**Prompt to attach with the PRD:**

> Continue Aniro and implement **Stage 3 only** from `Aniro-Build-Stages.md`. Use the attached PRD. Build Reflect from real Plan completion records, not hard-coded chart values. Add editable habits and colored streaks, module-level planned-versus-completed summaries, and deterministic respectful coach prompts. Build Money with user-entered LKR budget, editable expense categories and expense CRUD. Add JSON backup/export and CSV expense export. Keep the database fresh for new users. Test the calculations and inspect every page in a browser. Report the URL, checklist results, and gaps, then stop for my review. Do not begin integrations.

## Stage 4 — Google Calendar and optional AI (target 3–4 hours; external setup may extend)

**Build:** Google OAuth for a single user; read selected calendar events, create/update Aniro blocks with confirmation, store event IDs, reconnect and sync-error states; Gemini-backed **Abdaal** drawer using the PRD system prompt and minimal user-approved context; API key stored server-side; deterministic fallback on quota/API failure. The assistant identifies itself as an original AI, not Ali Abdaal.

**Review in browser:**

- [ ] Connecting/disconnecting Google leaves local planning usable.
- [ ] Existing Google events appear; a confirmed Aniro block creates only one Google event.
- [ ] Editing or deleting a synced block has a clear, predictable Google Calendar result.
- [ ] Abdaal gives short, context-grounded answers and never changes records by chat alone.
- [ ] The context preview excludes raw spending, names, and private notes unless explicitly allowed.
- [ ] A missing Gemini key, free-tier limit, or lost network produces a useful fallback.

**Prompt to attach with the PRD:**

> Continue Aniro and implement **Stage 4 only** from `Aniro-Build-Stages.md`, following the attached PRD. Add single-user Google Calendar OAuth/sync and the optional Gemini-powered Abdaal drawer. Keep keys/tokens server-side and request narrow Google scopes. Never send sensitive finance or relationship details to Gemini without a specific opt-in. Use the PRD system prompt, short responses, and deterministic fallback. Do not claim Abdaal is Ali Abdaal. Verify real sync and one AI interaction only after I supply credentials; if credentials are unavailable, finish integration code and mock/local verification, report the exact external setup steps, and leave Stage 4 open rather than claiming live integration complete. Stop for review.

## Stage 5 — harden, deploy, and hand off (target 3–4 hours; hosting setup may extend)

**Build:** final accessibility/responsiveness pass, backup and restore test, migration test, error states, secret handling, production configuration, hosted deployment if chosen. Recommended hosted shape: Vercel for React; a Python-capable host for FastAPI; hosted PostgreSQL. Confirm free-tier terms at deployment time. Keep the local SQLite option fully usable. No paid upgrade without user authorization.

**Review in browser:**

- [ ] All four pages pass the previous checklists on desktop and phone-width browser.
- [ ] Fresh account starts empty; old account data survives migrations and redeploy.
- [ ] Export and restore round trip produces the same user records.
- [ ] API keys and Google tokens never appear in browser code, page source, logs, or exports.
- [ ] Hosted app uses HTTPS and account access protection; local app still works independently.
- [ ] One end-to-end journey works: Clarity goal → weekly goal → time block → completion → Reflect total → Money entry → Abdaal summary.
- [ ] User receives live URL (if deployed), repo/source location, start commands, backup instructions, and a list of known limitations.

**Prompt to attach with the PRD:**

> Finish **Stage 5 only** of Aniro using `Aniro-Build-Stages.md` and the attached `Aniro-PRD.md`. Preserve all existing data and completed features. Run the full end-to-end review, fix material issues, test backup/restore and migrations, then deploy the React frontend, FastAPI backend, and PostgreSQL database only if the required free hosting/accounts are available. Do not start a paid plan. Verify the live URL and access protection; keep the local SQLite version usable. Give me a concise handoff with URLs, start commands, backup/restore steps, tests, and remaining limitations. Do not call the product complete until the Stage 5 checklist passes.

## What to prepare before starting

1. **Stage 1:** a local development computer with Node.js and Python, plus a Git repository or a chosen workspace folder. No external account is needed.
2. **Stage 4:** a Google account and Google Cloud OAuth project/client for Calendar; a Gemini API key if you want live AI. Put secrets in local environment settings, never in chat or committed files. Decide what personal context Abdaal may send to Gemini.
3. **Stage 5:** decide whether Aniro remains local or goes online. For hosting, create the Vercel, Python-host, and database accounts you choose; decide how the single-user app will authenticate. Free tiers can change or pause, so verify current terms then.
4. **Content you can supply later:** exact BIT and Design module names, your first actual goals, preferred wisdom lines for each page, and the current month’s budget. These are entered through the app; they are not required to start development.

**Review protocol:** If a checkbox fails, send that observation to the builder in the **same stage** and ask for a fix. Advance only after you have opened the browser preview and accepted the stage. Avoid replacing the PRD midway; record agreed changes in it so later sessions have one source of truth.
