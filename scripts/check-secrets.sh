#!/usr/bin/env bash
# Repo-specific secret hygiene checks (CI runs gitleaks as well).
# Run from anywhere in the repo:  scripts/check-secrets.sh
# Prints file names and key names only, never values.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

failed=0
fail() {
  echo "::error::$*"
  failed=1
}

# 1. No env files are committed, except the .env.example templates.
tracked=$(git ls-files | grep -E '(^|/)\.env(\.[^/]+)?$' | grep -vE '(^|/)\.env\.example$' || true)
if [ -n "$tracked" ]; then
  fail "Env files are committed (remove them with 'git rm --cached', they hold secrets): $(echo $tracked)"
fi

# 2. .gitignore keeps ignoring env files in every folder.
for f in .env .env.local .env.production backend/.env frontend/.env.local; do
  git check-ignore -q --no-index "$f" || fail ".gitignore no longer ignores $f"
done

# 3. Templates hold no secret values: secret-looking keys are empty and the
#    database URL uses <placeholders>.
while IFS= read -r example; do
  while IFS= read -r line; do
    key=${line%%=*}
    value=${line#*=}
    case "$key" in
      VITE_*PUBLISHABLE*) ;;  # public by design
      *KEY* | *SECRET* | *PASSWORD* | *TOKEN*)
        [ -z "$value" ] || fail "$example: $key must be empty in the template" ;;
      *DATABASE_URL*)
        if [[ "$value" =~ ://[^:/@]+:([^@]*)@ ]] && [[ "${BASH_REMATCH[1]}" != *"<"* ]]; then
          fail "$example: $key holds a real-looking password; use a <placeholder>"
        fi ;;
    esac
  done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$example" || true)
done < <(git ls-files | grep -E '(^|/)\.env\.example$')

# 4. VITE_* variables are compiled into the public JavaScript bundle, so they
#    must never carry a secret.
leaky=$(git grep -lE 'VITE_[A-Z0-9_]*(SECRET|PASSWORD|PRIVATE|TOKEN|API_KEY|DATABASE)' -- . ':!scripts/check-secrets.sh' || true)
if [ -n "$leaky" ]; then
  fail "A secret-sounding VITE_ variable would ship to every browser. Found in: $(echo $leaky)"
fi

if [ "$failed" -ne 0 ]; then
  exit 1
fi
echo "Secret hygiene checks passed."
