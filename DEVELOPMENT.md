# Development guide

Everything needed to configure, test, and deploy GRE Prep, plus how its models and content work. For what the app does, see the [README](README.md); to run it, see [how_to_run.md](how_to_run.md).

**Contents**

- [Project layout](#project-layout)
- [Running the app](#running-the-app)
- [Configuration: Supabase and Clerk](#configuration-supabase-and-clerk)
- [Deploy on Vercel](#deploy-on-vercel)
- [CI (GitHub Actions)](#ci-github-actions)
- [How it works](#how-it-works)
  - [The comfort model](#the-comfort-model)
  - [Placement check](#placement-check)
  - [Practice: Verbal and Quant](#practice-verbal-and-quant)
  - [Word bank and study sets](#word-bank-and-study-sets)
  - [Pronunciation](#pronunciation)
  - [Your sentence](#your-sentence)
  - [AI features (Claude)](#ai-features-claude)
- [Adding a question type](#adding-a-question-type)

## Project layout

```
backend/                FastAPI (Python 3.12)
  app/routers/api.py      every API route
  app/services/           study loop, practice, placement, stats, study coach
  app/items/              question types (vocab, verbal, quant)
  app/vocab_engine/       FSRS-5 scheduler, word-comfort model, placement scoring
  app/seed/               word bank (vocab/) and question banks (verbal/, quant/)
  migrations/             Alembic migrations, applied on startup
  tests/                  pytest suite
frontend/               React + TypeScript + Vite, Tailwind CSS and shadcn/ui
  src/pages/              one file per page
  src/components/ui/      shadcn components (add more with `npx shadcn@latest add <name>`)
scripts/check-secrets.sh  secret hygiene check (also run in CI)
```

## Running the app

Quick start, Docker, running locally, the sign-in-free test stack, and the test commands are in **[how_to_run.md](how_to_run.md)**.

## Configuration: Supabase and Clerk

Both are switched on by configuration alone. Settings go in the root `.env` (template: `.env.example`). Secrets, meaning the database URL and the Claude key, are read only by `backend/app/secrets_config.py` and show as `**********` in logs and errors; everything else is in `backend/app/config.py`. The backend runs on PostgreSQL only: Supabase normally, or Docker's local Postgres. Without Clerk, set `GRE_AUTH_MODE=dev` to run with dev users. Clerk is the default, so a deployment never falls back to dev users by accident.

### Supabase

1. **Create a Supabase project.** Open **Connect** and copy a connection string. **Direct connection** (`db.<ref>.supabase.co`) is IPv6-only, so it fails on networks without IPv6, including Docker and Vercel. Use the **Session pooler** string (port 5432) locally and in Docker. On Vercel use the **Transaction pooler** (port 6543), which suits serverless; the backend refuses to start there with the direct host.
2. **Point the backend at it.** In `.env`, set:

   ```
   GRE_DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require
   ```

   The `postgresql://` URL Supabase shows is rewritten to use the psycopg 3 driver.
3. **Start the backend.** Alembic migrations run on startup; you can also run `alembic upgrade head` from `backend/`. Then the word and question banks sync.

Notes:
- **Row-level security.** Every table has RLS enabled with no policies. That blocks Supabase's auto-generated Data API (anyone with the anon key) from reading app data. The backend connects as the table owner, so RLS doesn't apply to it. All data access goes through FastAPI; the frontend never talks to Supabase directly. New tables must enable RLS in their migration (see `0007_word_sentences.py`); `test_row_level_security` checks every table.
- **Changing models.** After editing `app/models.py`, run `alembic revision --autogenerate -m "..."` from `backend/`. The test `test_migrations_match_models` fails if you forget.

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

## Deploy on Vercel

`vercel.json` deploys both halves as one Vercel project: `/api/*` goes to the FastAPI backend and everything else to the Vite frontend. Set these in the Vercel project's environment variables:

- **Backend:** `GRE_DATABASE_URL` (the Supabase **Transaction pooler** string, `…pooler.supabase.com:6543`; the direct connection is IPv6-only and Vercel can't reach it), `GRE_AUTH_MODE=clerk`, `GRE_CLERK_JWKS_URL`, `GRE_CLERK_ISSUER`, `GRE_ALLOWED_EMAILS`, `ANTHROPIC_API_KEY`. Add `GRE_CLERK_AUTHORIZED_PARTIES` only for a custom domain; the deployment's own Vercel URLs are accepted automatically.
- **Frontend:** `VITE_CLERK_PUBLISHABLE_KEY`. It is read at build time, so redeploy after changing it.

On Vercel the backend refuses to start unless Clerk sign-in and the approved-email list are configured, so a missing setting takes the app down instead of opening it up.

## CI (GitHub Actions)

`.github/workflows/ci.yml` runs on pushes to `main` and `dev`, on pull requests, weekly, and on demand (Actions → CI → Run workflow). It needs no secrets: the tests use a throwaway Postgres container and run with AI turned off. The four jobs:

- **Secret scan.** `scripts/check-secrets.sh` checks that no `.env` file is committed and that `.gitignore` still ignores them. It also checks that `.env.example` holds only empty values and `<placeholders>`, and that no secret-sounding `VITE_` variable exists, since those are built into the public JavaScript. Then [gitleaks](https://github.com/gitleaks/gitleaks) scans the commits for keys and passwords, using its default rules plus Clerk secret keys and database URLs with a password (`.gitleaks.toml`). The weekly run scans the whole history.
- **Backend tests.** `pytest` on Python 3.12 against Postgres 16.
- **Frontend lint and build.** `npm ci`, ESLint, then `tsc` and `vite build`.
- **Dependency vulnerabilities.** `pip-audit` on the pinned versions in `backend/constraints.txt`, and `npm audit` for high or critical issues in packages that ship to users.

To make CI required before merging: GitHub → Settings → Branches → add a rule for `main` → "Require status checks to pass", and pick the four jobs.

## How it works

### The comfort model

Each user–word pair has a `WordCard` (see `backend/app/vocab_engine/types.py`):

| Signal | Source |
|---|---|
| Memory strength (stability, difficulty, recall probability) | FSRS-5 (`vocab_engine/fsrs.py`) |
| Depth of knowledge: recognize → recall → discriminate → use | which quiz modes the user passes (`comfort.py: _update_depth`) |
| Fluency | response time vs. the user's own per-mode baseline (Welford on log ms) |
| Confidence calibration | Sure / Unsure / Guess tap before the answer is revealed |

- **Ratings.** Every answer is turned into an FSRS rating automatically (`implicit_rating`).
- **Depth.** A word climbs one depth level after 2 correct answers at least 6 hours apart, and drops below a level when the user fails it.
- **Question choice.** The quiz mode is chosen at the user's frontier 70% of the time (`choose_mode`). The modes are flashcard, meaning (pick the definition), cloze (pick the word that completes a sentence), synonyms (pick the two closest words), and usage (write a sentence, graded by Claude). The Vocab page's format switch (Mixed, Flashcards, Multiple choice) narrows the choice (`mode_chain`).
- **Confusions.** Wrong picks are logged in `confusions` and reused as distractors.
- **Score.** The comfort score is 0–100: `0.45·R + 0.30·depth + 0.15·stability + 0.10·calibration`. Tiers are Learning (<40), Shaky, Comfortable (65+), and Mastered (85+).
- **Daily limit.** New words per day come from the profile (`daily_new_words`, default 10). "Study more" adds extra new words for the current day only.

### Placement check

The placement check (`/placement`) has 20 adaptive questions. Each one asks you to pick a word's definition, with an "I don't know" option.

- **Estimating your level.** The engine (`vocab_engine/placement.py`) estimates ability θ with a one-parameter IRT model. The model assumes a 20% guessing floor and an N(0,1) prior, and averages over a grid of possible θ values (an EAP estimate). Each next word is the unseen word whose difficulty is closest to the current estimate.
- **Word difficulty.** A word's difficulty is its tier prior (0 / 0.7 / 1.5) plus a learned offset (`Word.global_difficulty`). Every placement answer adjusts that offset with an Elo-style update.
- **After the check.** Words you answered correctly become `placement` cards. They skip the learning steps and come back in 2 days for a recall check.
- **Fast-tracking.** Later, a new word you're predicted to know with at least 75% probability becomes a `fast_track` card: no flashcard, straight to a recall question. Fast-tracked cards don't count toward the daily new-word limit but are capped at twice it.
- **Accuracy.** In simulations, the estimate is accurate to about ±0.45 for typical users after 20 questions. Very strong users are underestimated, because the bank has only three difficulty levels and its hardest words sit at 1.5. That error makes fast-tracking more cautious, which is the safe direction, and it should shrink as difficulties are learned.

### Practice: Verbal and Quant

The Practice page (`/practice`) serves original questions from `backend/app/seed/`, synced into the `items` table on startup and matched by slug. A Verbal / Quant switch picks the section; `?section=quant&kind=qc` links straight to a type.

| Section | Type | Count | Source file |
| --- | --- | --- | --- |
| Verbal | Text Completion (`tc`) | 25 | `verbal/text_completion.json` |
| Verbal | Sentence Equivalence (`se`) | 15 | `verbal/sentence_equivalence.json` |
| Verbal | Reading Comprehension (`rc`) | 12, on 3 passages | `verbal/reading_comprehension.json` |
| Quant | Quantitative Comparison (`qc`) | 6 | `quant/comparison.json` |
| Quant | Multiple choice (`qmc`) | 6 | `quant/multiple_choice.json` |
| Quant | Numeric entry (`qne`) | 5 | `quant/numeric_entry.json` |

- **Format and scoring.**
  - Text Completion has 1–3 blanks: 5 choices for one blank, 3 per blank otherwise. You only get credit if every blank is right.
  - Sentence Equivalence has 6 choices; you pick the two that each complete the sentence with the same meaning. Every SE question includes a trap pair: two synonyms that fit together but not the sentence.
  - Reading Comprehension questions ask you either to pick one of 5 choices or to select every right choice of 3. All the questions on a passage are served together, in order.
  - Quant comparisons use the GRE's four fixed choices. Multiple-choice questions either have one answer of 5 or ask for all that apply. Numeric entry accepts any equivalent value, so `4/36` counts for `1/9`.
  - "Select all" questions need every right choice and no wrong ones.
- **Authoring.**
  - Verbal: the first option of each blank (TC), the first two options (SE), and the first option(s) of each RC question are correct. Options are shuffled when a question is served.
  - Quant: answers are stated explicitly, because options stay in their written order (numbers ascending, as on the GRE).
  - Every question has a clue (the hint) and an explanation. Quant questions also carry a topic (arithmetic, algebra, geometry, data) and an optional table.
  - `validate_items` in `app/seed/items.py` enforces the format.
- **Ratings.**
  - Each user has a rating per question type (`user_skills`: `verbal.tc`, `quant.qc`, …). Verbal ratings start from the placement level when there is one; Quant ratings start at 0.
  - Questions are picked near the rating, unseen first, and nothing answered in the last 14 days is repeated.
  - After each answer, an Elo update moves both the rating and the question's learned difficulty. The update allows for the chance of guessing right: 1/5 for five choices, 1/4 for comparisons, 1/15 for SE, and none for numeric entry.
  - Answers that used the hint, or asked the study coach about the question first, count half.
- **Separate stats.** Practice answers go into `attempts`, tagged with their section, but don't count toward the dashboard's vocabulary numbers.

### Word bank and study sets

1,057 words in `backend/app/seed/vocab/words_*.json`. The server validates and syncs the bank on startup: new words are added, changed entries are updated, and nothing is deleted.

- **Study sets.** Words are studied in 37 numbered sets (`assign_sets` in `app/seed/seed.py`). The first 32 follow GregMat's vocabulary groups (`groups.json`); only the word lists and their grouping come from there, and every entry is written separately. The remaining words follow in sets of about 25 that never mix frequency tiers. New words come from the current set until it's fully started.
- **Frequency tiers.** Each word has a tier: 1 = high frequency (279 words), 2 = medium (656), 3 = advanced (122). Words tagged `"freq_source": "magoosh_top20"` are Magoosh's public "Top 20 most tested GRE words"; the other tiers are editorial judgments.
- **Clusters and families.** A cluster groups near-synonyms (565 clusters). A family groups clusters that are easy to confuse, such as *soothe* and *ease* (74 families). Quiz distractors never come from the target's own family, and no two options are listed synonyms of each other. As a result, every synonym-pair question has exactly one right pair.
- **Common phrases.** Each word lists 2–4 phrases showing how it's most often used in real writing, such as *widely lauded* or *a false dichotomy*, never pairings that are merely grammatical. Every phrase must contain the word itself or a regular inflection of it (*lauded*, *extolled*).
- **Checks.** `validate_bank` in `app/seed/seed.py` enforces these rules. One example: a synonym that is itself a bank word must belong to the same family.
- **Growing the bank.** `backend/scripts/generate_words.py` drafts new entries with Claude: one call writes each entry and a second, independent call reviews it.

### Pronunciation

Every word has a stress-marked respelling (`"pronunciation": "luh-KAH-nik"` in the word bank, shown as luh-**kah**-nik) and a speaker button to hear it.

- **Respellings.** Variants are joined with " or ", as in `REK-un-dyt or rih-KAHN-dyt`. `validate_bank` requires exactly one capitalized, stressed syllable per variant.
- **Speech.** The speaker button uses the browser's built-in voice (`src/lib/speech.ts`), preferring Apple's US voices (Samantha, Ava, …). It works in Safari on macOS, iOS and iPadOS and in other modern browsers, with no API key.
- **iPhone/iPad.** Safari's speech follows the ring/silent switch, so the first tap on those devices shows a one-time hint.
- **Where it appears.** Flashcards, meaning and usage questions, word cards, and the placement check. It's left out of cloze and synonym questions, where hearing the word would give away the answer.

### Your sentence

Students can save their own sentence with any word (`word_sentences` table, `PUT /api/words/{id}/sentence`, at most 500 characters). Like the definition, it stays hidden until the answer is revealed: it shows on the answer screen, on the back of flashcards, and on the word page. The study coach can see it when talking about that word.

### AI features (Claude)

- **Study coach** (`app/services/coach.py`, `src/components/Coach.tsx`, `src/lib/coach.tsx`). The home page is the coach's chat; every other page has it as a chat bubble. Both show the same conversation, which is saved per account (`coach_messages`) so it survives a refresh.
  - **Context.** Every message comes with a snapshot of the student's progress: plan, vocab sets and comfort tiers, practice ratings, and placement level. Tools let it look further: set-by-set progress, weak words and confused pairs, recent activity, word entries, and a student's history with one word.
  - **What's on screen.** Pages tell the coach what they show (`useCoachPage`): the Vocab or Practice question, or the word page. On a question it won't give the answer away before the student answers, and asking counts as a hint.
  - **Actions, confirmed with a button.** The coach only offers; nothing changes until the student clicks. It can offer plan changes (`propose_plan`), bring started words back for review now (`review_now`, `POST /api/study/review-now`), mark a word as known (`mark_known`, `POST /api/words/{id}/known`), change the Vocab study settings (`propose_study_settings`, saved in the browser), save the student's sentence (`save_sentence`), and link to a Practice type (`open_practice`). Offers are saved with the reply (`coach_messages.actions`).
  - **Notes.** It keeps short notes about the student between chats (`remember` / `forget`, `coach_notes` table, at most 30). They're sent with every message, and the student can see and delete them from the chat's notes button (`GET` / `DELETE /api/coach/notes`).
  - **Streaming.** `POST /api/coach/chat/stream` sends the reply as server-sent events while it's written: text pieces, a status line while a tool runs, then a final event with the whole reply and any offers. `POST /api/coach/chat` returns the same final result in one response.
  - **Prompt caching.** The instructions and tool definitions are cached. What changes each turn (snapshot, page, notes) goes in a system message after the student's message, and the conversation is cached up to the latest message, so earlier turns and tool steps are reused.
  - **Scope.** It stays on progress, planning, the GRE, and vocabulary, and politely declines anything else.
- **Usage grading** (`ai.py`). Judges a sentence the student writes with a word, returning structured JSON.
- **Mnemonics** (`ai.py`). One memorable sound-alike or image per word, on request.

All of them use `claude-opus-5-5` by default (`GRE_CLAUDE_MODEL`), with server-side refusal fallbacks turned on. Prompts always include the word's verified entry, so Claude explains the app's answer key instead of inventing its own. Set `GRE_AI_ENABLED=false` to run without credentials; the coach and mnemonics are then hidden, and usage questions are never served.

**Daily limit.** Each student gets `GRE_AI_DAILY_LIMIT` Claude requests per day (default 60, reset at midnight UTC; `0` turns it off). A request is one coach message, mnemonic, or graded sentence, however many API calls it takes. Requests and tokens, including cache reads and writes, are recorded per student per day in `ai_usage` (`app/services/limits.py`). Past the limit the coach and mnemonics return 429, and Vocab stops serving questions that need Claude to grade them; one already on screen is still graded.

## Adding a question type

Question formats are `ItemType`s registered in `backend/app/items/` (`vocab.py`, `verbal.py`, `quant.py`). Each one builds a question's payload and answer key, grades a response, and optionally gives a hint. For a new bank-backed type:

1. Add the type in `app/items/`, and its bank file under `app/seed/`.
2. Register the bank in `BANKS` in `app/seed/items.py`, and add its checks to `validate_items`.
3. Add the type to `MIXES` and `guess_rate` in `app/services/practice.py`, and to `PracticeKind` in `app/routers/api.py`.
4. Render it in `frontend/src/components/PracticeFormats.tsx`, and add its tab in `frontend/src/pages/Practice.tsx`.

The `attempts` log, the `skills` tree, `issued_items`, and the profile are shared across sections, so a Writing section can follow the same pattern.
