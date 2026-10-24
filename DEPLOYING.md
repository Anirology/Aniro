# Deploy Aniro on Vercel

Aniro uses Vercel Services: a Vite frontend and a FastAPI backend on the same
origin. The backend requires persistent Postgres storage in production. The
repository's local SQLite database and `.env` are intentionally excluded from
deployment.

## Vercel setup

1. Import the repository with the repository root as the project root. The
   root `vercel.json` defines both services and routes `/api/*` to FastAPI.
2. Enable **Vercel Authentication → All Deployments** before using the project.
   Aniro is a single-user personal app and its API has no public user accounts.
3. Connect a Neon Postgres database to the project for Production and Preview.
   The Neon integration supplies `DATABASE_URL`. Use a separate preview
   database if previews will receive writes.
4. Add these environment variables to Production:
   - `ANIRO_PUBLIC_URL=https://<your-production-domain>`
   - `ANIRO_TOKEN_KEY=<a stable, random 32-byte URL-safe base64 key>`
   - `ANIRO_GOOGLE_CLIENT_ID`, `ANIRO_GOOGLE_CLIENT_SECRET`, and
     `ANIRO_GOOGLE_ALLOWED_EMAIL` for Google Calendar.
   - `ANIRO_GEMINI_API_KEY` only if the AI coach is wanted.
5. Deploy. A new empty Postgres database is initialized once on backend
   startup. Existing databases are never silently overwritten.
6. Add the production callback
   `https://<your-production-domain>/api/integrations/google/callback` to the
   Google OAuth web client. Connect Google again from Plan. Local Windows token
   ciphertext is never copied to the hosted app.
7. If moving local records, export JSON from local Reflect and restore it in
   the protected hosted app. This transfers tasks, goals, habits, budgets, and
   expenses. Keep the local export until counts and records match. The restore
   saves a snapshot of the previous hosted records.

Use a domain already owned by the Vercel team, or the project's free
`*.vercel.app` production address. Buying a custom domain is a separate
purchase.

## Current hosted setup

- Private app: `https://aniro-topaz.vercel.app/` (Vercel Authentication, all deployments).
- Public app information and privacy policy: `https://aniro-info.vercel.app/`
  and `https://aniro-info.vercel.app/privacy.html`. The separate `aniro-info`
  Vercel project uses this repository's `public-info` directory.
- Google OAuth production callback:
  `https://aniro-topaz.vercel.app/api/integrations/google/callback`.
- Google OAuth uses the `aniro-512005` Google Cloud project. The public info
  URLs and both Vercel domains are registered in its Branding settings.
- The hosted database started empty; local SQLite records were not transferred.

Google's OAuth app is published as External / In production. Google may still
show an unverified-app warning until its branding and sensitive-scope review
is approved. The dashboard itself remains restricted to the Vercel team.
