# HotCrowd

Digital signage CMS: pair a player, upload media, build a playlist, assign it, play it.

```
apps/api          FastAPI + SQLAlchemy (existing Neon tables)
apps/web          Next.js App Router CMS
packages/contracts  Shared TS types
```

The player calls `/api/player/...` on the **API origin**, not the Next.js origin.

## Run locally

1. Copy `.env.example` to `.env` and set `DATABASE_URL` (Neon) and `SECRET_KEY`.
2. API:

```bash
cd apps/api
uv sync
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Existing Django/Neon databases should be stamped, not reset:

```bash
cd apps/api
uv run alembic stamp head
```

In `DEBUG=True`, the API also creates missing tables on startup so a local sqlite file works without stamping.

3. Web:

```bash
pnpm install
pnpm dev:web
```

Open `http://127.0.0.1:3000`. Next rewrites `/api/*` and `/media/*` to the API so CMS cookies stay first-party.

## Production

Set `DEBUG=False` on the API. Startup refuses a weak `SECRET_KEY`, sqlite `DATABASE_URL`, or a localhost `PUBLIC_API_URL`.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Neon Postgres |
| `SECRET_KEY` | JWT signing |
| `PUBLIC_API_URL` | Absolute origin baked into player playlist URLs |
| `CORS_ORIGINS` | Player web origin only |
| `PUBLIC_WEB_URL` | CMS origin used in password-reset emails |
| `EMAIL_HOST` (optional) | SMTP for reset mail; if empty, links print in the API log |
| `USE_S3=True` plus `R2_*` | Cloudflare R2 for uploads (same keys Django used) |
| `STRIPE_SECRET_KEY` / `STRIPE_PRICE_PRO` | Pro checkout. In DEBUG without Stripe, Upgrade sets Pro locally |
| `INSTAGRAM_APP_ID` | Optional OAuth app id; Graph token paste works without it |

Auth is an httpOnly access cookie (`hc_access`, 15 minutes) plus a refresh cookie (`hc_refresh`, 14 days). The CMS retries `/api/v1/auth/refresh` on 401. Logout clears both.

Run the API image (or `uvicorn`) and host `apps/web` on Vercel or in Compose. Point the existing player at the API host. Assigned playlists only play when they are published (`ACTIVE`) and inside any scheduled window; otherwise the store fallback (logo, custom URL, or black) is returned as `{url, type, duration, position}`.

If an account password was ever committed in tests, change it in the database (hashes are Django `pbkdf2_sha256`; login rehashes weaker iteration counts).

## Docker

Local:

```bash
docker compose up --build
```

Compose forces `DEBUG=true` for the API. Production deploys should pass `DEBUG=false` and the variables above.
