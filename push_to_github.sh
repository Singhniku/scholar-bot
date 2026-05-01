#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# push_to_github.sh
#
# 1. Run the full test suite (skills/ folder)
# 2. If all tests pass → commit everything, push to main, done
# 3. If tests fail → print report and exit non-zero (nothing is pushed)
#
# Usage:
#   chmod +x push_to_github.sh
#   ./push_to_github.sh                        # auto-generates commit message
#   ./push_to_github.sh "feat: my message"     # custom commit message
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'

log()  { echo -e "${GREEN}[push]${NC} $*"; }
warn() { echo -e "${YELLOW}[push]${NC} $*"; }
fail() { echo -e "${RED}[push] FAILED:${NC} $*"; exit 1; }

# ── 1. Run tests ──────────────────────────────────────────────────────────────
log "Running test suite…"
if ! python3 -m pytest skills/ -v --tb=short 2>&1; then
    fail "Tests failed — nothing was pushed. Fix the failing tests and try again."
fi
log "All tests passed ✓"

# ── 2. Stage everything (respects .gitignore) ─────────────────────────────────
log "Staging changes…"
git add \
    src/ \
    skills/ \
    app.py \
    main.py \
    config.py \
    requirements.txt \
    .env.example \
    .gitignore \
    README.md \
    push_to_github.sh \
    2>/dev/null || true

# Check if there is anything to commit
if git diff --cached --quiet; then
    warn "Nothing new to commit — working tree is clean."
    exit 0
fi

# ── 3. Commit ─────────────────────────────────────────────────────────────────
TIMESTAMP="$(date '+%Y-%m-%d %H:%M')"
if [ -n "${1:-}" ]; then
    MSG="$1"
else
    # Auto-generate a message from what changed
    CHANGED="$(git diff --cached --name-only | head -8 | tr '\n' ', ' | sed 's/,$//')"
    MSG="chore: update ${CHANGED} [${TIMESTAMP}]"
fi

log "Committing: ${MSG}"
git commit -m "${MSG}"

# ── 4. Push to main ───────────────────────────────────────────────────────────
REMOTE="${REMOTE:-origin}"
BRANCH="${BRANCH:-main}"

log "Pushing to ${REMOTE}/${BRANCH}…"

# Create remote branch if it doesn't exist yet
if ! git ls-remote --exit-code "$REMOTE" "$BRANCH" &>/dev/null; then
    warn "Remote branch '$BRANCH' not found — creating it."
    git push -u "$REMOTE" HEAD:"$BRANCH"
else
    git push "$REMOTE" HEAD:"$BRANCH"
fi

log "Published to GitHub: https://github.com/Singhniku/scholar-bot/tree/${BRANCH}"
