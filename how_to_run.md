# How to run GRE Prep

The quickest way is Docker. To run the backend and frontend yourself, see [Run it locally](#run-it-locally-without-docker). For what the app does, see the [README](README.md); for configuration, deployment and how it works, see the [development guide](DEVELOPMENT.md).

**Contents**

- [Quick start](#quick-start)
- [Run it with Docker](#run-it-with-docker)
- [Run it locally](#run-it-locally-without-docker)
- [Testing without signing in](#testing-without-signing-in)
- [Tests](#tests)

## Quick start

```bash
cp .env.example .env        # optional: add ANTHROPIC_API_KEY for the AI features
docker compose up --build
```

Then open **http://localhost:8080**. The template starts the app without sign-in (dev mode); to use Supabase and Clerk, see [Configuration](DEVELOPMENT.md#configuration-supabase-and-clerk).

## Run it with Docker

```bash
docker compose up --build
```

Then open http://localhost:8080. The stack has three containers:

| Service | What it runs |
|---|---|
| `frontend` | The production React build, served by unprivileged nginx on :8080. It also proxies `/api` to the backend, so the browser sees one origin. |
| `backend` | FastAPI. It runs as a non-root user, applies migrations on startup, and isn't published to the host. |
| `db` | PostgreSQL 16, like Supabase's, on a persistent `db-data` volume. |

How configuration flows:
- **Clerk publishable key.** Compose reads the root `.env` and passes `VITE_CLERK_PUBLISHABLE_KEY` to the frontend build. It's public by design, so it's fine to bake into the JavaScript.
- **Backend settings.** The backend container gets the root `.env` as its environment when it starts. Env files are excluded from both images by their `.dockerignore` files.
- **Database.** Docker uses its own `db` service. To use Supabase instead, add `DATABASE_URL=<session pooler string>` to the command's environment.
- **Serving from another address.** Set `APP_ORIGIN` (default `http://localhost:8080`) so Clerk tokens from that site are accepted.

To start fresh with an empty database, run `docker compose down -v`.

## Run it locally (without Docker)

All settings live in one `.env` at the repository root, shared by the backend and the frontend:

```bash
cp .env.example .env                            # set GRE_DATABASE_URL (Supabase); ANTHROPIC_API_KEY for AI

# backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt -c constraints.txt
.venv/bin/uvicorn app.main:app --reload --port 8000

# frontend (second terminal)
cd frontend
npm install
npm run dev                                     # http://localhost:5173, proxies /api to :8000
```

On startup the backend applies migrations, then syncs the word bank and the question banks into the database.

### Testing without signing in

With Clerk on, the main dev stack (backend on :8000, frontend on :5173) requires sign-in. For browser testing without it, run a second stack on :8001 and :5174 in dev-auth mode. It never touches the Clerk setup. Give it its own database so dev users never land in Supabase: Docker's local Postgres works (`docker compose up -d db`, reachable on port 5433). Environment variables override the `.env` file:

```bash
docker compose up -d db
cd backend && GRE_AUTH_MODE=dev GRE_DATABASE_URL=postgresql://gre:gre@localhost:5433/gre .venv/bin/uvicorn app.main:app --port 8001
cd frontend && VITE_CLERK_PUBLISHABLE_KEY= GRE_API_TARGET=http://localhost:8001 npm run dev -- --port 5174
```

## Tests

```bash
cd backend && .venv/bin/pytest            # engine, API, question types, migrations, coach
cd frontend && npm run lint && npm run build
scripts/check-secrets.sh                  # from the repository root
```

- **Database.** `pytest` runs on a throwaway local PostgreSQL (the `pgserver` dev dependency), never on Supabase. Set `GRE_TEST_DATABASE_URL` to use an existing empty database instead, as CI does with a service container.
- **AI.** Tests run with AI turned off. Tests of Claude features replace the Messages API with a fake that replays canned responses, so the suite never spends API credits.
