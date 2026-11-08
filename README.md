# GRE Prep

AI-assisted GRE prep. The first section is vocabulary, driven by an adaptive
model that learns how comfortable each user is with each word. The core is
built to add Quant and Writing later.

```
backend/    FastAPI (Python): API, item types, study loop, Claude integration
            app/vocab_engine/: FSRS-5 scheduler, word-comfort model, placement scoring
frontend/   React + TypeScript + Vite, styled with Tailwind CSS and shadcn/ui
            src/components/ui/: shadcn components (add more with `npx shadcn@latest add <name>`)
```

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

Tests:

```bash
cd backend && .venv/bin/pytest     # engine, API and item types
```

## How the comfort model works

Each user–word pair has a `WordCard` (see `backend/app/vocab_engine/types.py`):

| Signal | Source |
|---|---|
| Memory strength (stability, difficulty, recall probability) | FSRS-5 (`vocab_engine/fsrs.py`) |
| Depth of knowledge: recognize → recall → discriminate → use | which quiz modes the user passes (`comfort.py: _update_depth`) |
| Fluency | response time vs. the user's own per-mode baseline (Welford on log ms) |
| Confidence calibration | Sure / Unsure / Guess tap before the answer is revealed |

Every answer is turned into an FSRS rating automatically (`implicit_rating`).
A word climbs one depth level after 2 correct answers at least 6 hours apart, and drops below a level when the user fails it.
The quiz mode is chosen at the user's frontier 70% of the time (`choose_mode`).
Wrong picks are logged in `confusions` and reused as distractors.
The comfort score is 0–100: `0.45·R + 0.30·depth + 0.15·stability + 0.10·calibration`.
Tiers are Learning (<40), Shaky, Comfortable (65+), and Mastered (85+).

## Pronunciation

Every word has a stress-marked respelling (`"pronunciation": "luh-KAH-nik"` in the word bank, shown as luh-**kah**-nik) and a 🔊 button.

- **Respellings.** Variants are joined with " or ", as in `REK-un-dyt or rih-KAHN-dyt`. `validate_bank` requires exactly one capitalized, stressed syllable per variant.
- **Speech.** The 🔊 button uses the browser's built-in voice (`src/lib/speech.ts`), preferring Apple's US voices (Samantha, Ava, …). It works in Safari on macOS, iOS and iPadOS and in other modern browsers, with no API key.
- **iPhone/iPad.** Safari's speech follows the ring/silent switch, so the first tap on those devices shows a one-time hint.
- **Where it appears.** Flashcards, meaning and usage questions, word cards, and the placement check. It's left out of cloze and synonym questions, where hearing the word would give away the answer.

## Testing without signing in

With Clerk on, the main dev stack (backend on :8000, frontend on :5173) requires sign-in. For browser testing without it, run a second stack on :8001 and :5174 in dev-auth mode. It never touches the Clerk setup. Give it its own database so dev users never land in Supabase: Docker's local Postgres works (`docker compose up -d db`, reachable on port 5433). Environment variables override the `.env` file:

```bash
docker compose up -d db
cd backend && GRE_AUTH_MODE=dev GRE_DATABASE_URL=postgresql://gre:gre@localhost:5433/gre .venv/bin/uvicorn app.main:app --port 8001
cd frontend && VITE_CLERK_PUBLISHABLE_KEY= GRE_API_TARGET=http://localhost:8001 npm run dev -- --port 5174
```

## Verbal practice: Text Completion and Sentence Equivalence

The Practice page (`/practice`) serves original questions from `backend/app/seed/verbal/`: 25 Text Completion and 15 Sentence Equivalence. They're synced into the `items` table on startup, matched by slug.

- **Format and scoring.** Text Completion has 1–3 blanks: 5 choices for one blank, 3 per blank otherwise, with credit only if every blank is right. Sentence Equivalence has 6 choices; you pick the two that each complete the sentence with the same meaning. Every SE question includes a trap pair: two synonyms that fit together but not the sentence.
- **Authoring.** The first option of each blank (TC) or the first two options (SE) are correct; options are shuffled when a question is served. Each question has a clue (the hint) and an explanation. `validate_items` in `app/seed/items.py` enforces the format.
- **Ratings.** Each user has a rating per skill (`user_skills`: `verbal.tc`, `verbal.se`), starting from the placement level when there is one. Questions are picked near the rating, unseen first, with nothing answered in the last 14 days repeated. After each answer, an Elo update in the engine moves both the rating and the question's learned difficulty, using the chance of guessing right (1/5, 1/9, 1/27 for 1–3 blanks; 1/15 for SE). Answers that used the hint count half.
- **Separate stats.** Practice answers go into `attempts` but don't count toward the dashboard's vocabulary numbers.

## Placement check

The placement check (`/placement`) has 20 adaptive questions. Each one asks you to pick a word's definition, with an "I don't know" option.

- **Estimating your level.** The engine (`vocab_engine/placement.py`) estimates ability θ with a one-parameter IRT model. The model assumes a 20% guessing floor and an N(0,1) prior, and averages over a grid of possible θ values (an EAP estimate). Each next word is the unseen word whose difficulty is closest to the current estimate.
- **Word difficulty.** A word's difficulty is its tier prior (0 / 0.7 / 1.5) plus a learned offset (`Word.global_difficulty`). Every placement answer adjusts that offset with an Elo-style update.
- **After the check.** Words you answered correctly become `placement` cards. They skip the learning steps and come back in 2 days for a recall check.
- **Fast-tracking.** Later, a new word you're predicted to know with at least 75% probability becomes a `fast_track` card: no flashcard, straight to a recall question. Fast-tracked cards don't count toward the daily new-word limit but are capped at twice it.
- **Accuracy.** In simulations with the current bank, the estimate is accurate to about ±0.45 for typical users after 20 questions. Very strong users are underestimated, because the bank has only three difficulty levels and its hardest words sit at 1.5. That error makes fast-tracking more cautious, which is the safe direction, and it should shrink as difficulties are learned and more advanced words are added.

## Word bank

340 words in `backend/app/seed/vocab/`. The server validates and syncs the bank on startup: new words are added, changed entries are updated, and nothing is deleted.

- **Frequency tiers.** Each word has a tier: 1 = high frequency (160 words), 2 = medium (156), 3 = advanced (24). New words are introduced high-frequency first.
- **Where the tiers come from.** Words tagged `"freq_source": "magoosh_top20"` are Magoosh's public "Top 20 most tested GRE words"; all 20 are in the bank. Magoosh's Common/Basic/Advanced flashcard decks don't publish their word lists. The other tiers are editorial judgments to review.
- **Clusters and families.** A cluster groups near-synonyms. A family groups clusters that are easy to confuse, such as *soothe* and *ease*. Quiz distractors never come from the target's own family, and no two options are listed synonyms of each other. As a result, every synonym-pair question has exactly one right pair.
- **Common phrases.** Each word lists 2–4 phrases showing how it's most often used in real writing, such as *widely lauded* or *a false dichotomy*, never pairings that are merely grammatical. They appear on the word page and the back of the flashcard, and the AI tutor sees them too. Every phrase must contain the word itself or a regular inflection of it (*lauded*, *extolled*).
- **Checks.** `validate_bank` in `app/seed/seed.py` enforces these rules. One example: a synonym that is itself a bank word must belong to the same family.

## Adding a section later

Question formats are `ItemType`s in `backend/app/items/`. Register new types,
such as Text Completion, Quantitative Comparison, or an essay graded by Claude,
next to `vocab.py`. The `attempts` log, `skills` tree, `issued_items`, and
profile (`target_quant` is already there) are section-agnostic.

## AI (Claude)

`backend/app/services/ai.py` contains three features:
- the word tutor
- usage grading with structured JSON output
- mnemonics

All three default to `claude-opus-5-5` (`GRE_CLAUDE_MODEL`), with server-side refusal fallbacks turned on.
Prompts always include the word's verified entry.
`backend/scripts/generate_words.py` grows the word bank: one Claude call writes each entry and a second, independent call reviews it.
Set `GRE_AI_ENABLED=false` to run without credentials. Usage questions are then never served.

## Deploy on Vercel

`vercel.json` deploys both halves as one Vercel project: `/api/*` goes to the FastAPI backend and everything else to the Vite frontend. Set these in the Vercel project's environment variables:

- Backend: `GRE_DATABASE_URL` (the Supabase **Transaction pooler** string, `…pooler.supabase.com:6543`; the Direct connection is IPv6-only and Vercel can't reach it), `GRE_AUTH_MODE=clerk`, `GRE_CLERK_JWKS_URL`, `GRE_CLERK_ISSUER`, `GRE_ALLOWED_EMAILS`, `ANTHROPIC_API_KEY`. Add `GRE_CLERK_AUTHORIZED_PARTIES` only for a custom domain; the deployment's own Vercel URLs are accepted automatically.
- Frontend: `VITE_CLERK_PUBLISHABLE_KEY`. It is read at build time, so redeploy after changing it.

On Vercel the backend refuses to start unless Clerk sign-in and the approved-email list are configured, so a missing setting takes the app down instead of opening it up.

## Supabase (database) and Clerk (accounts)

Both are switched on by configuration alone. Settings go in the root `.env` (template: `.env.example`). Secrets, meaning the database URL and the Claude key, are read only by `backend/app/secrets_config.py` and show as `**********` in logs and errors; everything else is in `backend/app/config.py`. The backend runs on PostgreSQL only: Supabase normally, or Docker's local Postgres. Without Clerk, set `GRE_AUTH_MODE=dev` to run with dev users. Clerk is the default, so a deployment never falls back to dev users by accident.

### Supabase

1. **Create a Supabase project.** Open **Connect** and copy a connection string. **Direct connection** is IPv6-only: fine on a Mac with IPv6, but Docker needs the **Session pooler** string, which works over IPv4. On Vercel use the **Transaction pooler** (port 6543), which suits serverless; the backend refuses to start there with the direct host.
2. **Point the backend at it.** In `.env`, set:

   ```
   GRE_DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require
   ```

   The `postgresql://` URL Supabase shows is rewritten to use the psycopg 3 driver.
3. **Start the backend.** Alembic migrations run on startup; you can also run `alembic upgrade head`. Then the word and question banks sync.

Notes:
- **Row-level security.** Migration `0002` enables RLS, with no policies, on every table. That blocks Supabase's auto-generated Data API (anyone with the anon key) from reading app data. The backend connects as the table owner, so RLS doesn't apply to it. All data access goes through FastAPI; the frontend never talks to Supabase directly.
- **Changing models.** After editing `app/models.py`, run `alembic revision --autogenerate -m "..."` from `backend/`. The test `test_migrations_match_models` fails if you forget.
- **Tests.** `.venv/bin/pytest` runs on a throwaway local PostgreSQL (the `pgserver` dev dependency), never on Supabase. Set `GRE_TEST_DATABASE_URL` to use an existing empty database instead, e.g. a CI service container.

### Clerk

1. **Create a Clerk application** and choose your sign-in methods.
2. **Frontend.** Put the publishable key in `.env`:

   ```
   VITE_CLERK_PUBLISHABLE_KEY=pk_test_...
   ```

   The app then shows Clerk sign-in and an account menu, and sends each API request with the session token (`src/lib/auth.tsx`).
3. **Backend.** In `.env`, set:

   ```
   GRE_AUTH_MODE=clerk
   GRE_CLERK_ISSUER=<Frontend API URL>
   GRE_CLERK_JWKS_URL=<Frontend API URL>/.well-known/jwks.json
   GRE_CLERK_AUTHORIZED_PARTIES=["http://localhost:5173"]
   ```

   No Clerk secret key is needed: tokens are verified against Clerk's public signing keys, including expiry, issuer, and authorized party (`app/auth.py`).

Notes:
- **Mismatches are flagged.** If the frontend and backend disagree on auth mode, the app shows a warning banner.
- **User ids.** User ids are Clerk ids such as `user_2abc...`. Data from dev users isn't moved over to Clerk accounts.
- **Not built yet.** There's no Clerk webhook to delete a user's data when their Clerk account is deleted.

### Who can use the app

Access is limited in two layers. Clerk's sign-up restrictions only stop *new* accounts, so the backend check is what actually locks the app:

1. **Clerk sign-up is invite-only** (`sign_up_mode: restricted`). Strangers can't create accounts; add people with Clerk invitations.
2. **The backend approves specific emails.** `GRE_ALLOWED_EMAILS` in `.env` lists the accounts that may use the app. Clerk's session token carries the user's email (`primaryEmail` claim, set under Clerk → Sessions), and the backend returns 403 for anyone else, including accounts that already exist. The app then shows an "Access not approved" screen with a sign-out button. An empty list means any signed-in Clerk user.

To give someone access, invite them in Clerk and add their email to `GRE_ALLOWED_EMAILS`, then restart the backend.
