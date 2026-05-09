#!/usr/bin/env bash
# Scholar-Bot one-command setup — works on macOS and Linux.
#   curl -fsSL https://raw.githubusercontent.com/Singhniku/scholar-bot/main/setup.sh | bash
# OR after cloning:
#   ./setup.sh

set -e

# ── Colors ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

say()  { echo -e "${BLUE}▶${NC} $1"; }
ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1"; exit 1; }

# ── Check Python ────────────────────────────────────────────────────────────
say "Checking Python (need 3.10+)..."
if ! command -v python3 &>/dev/null; then
    fail "python3 not found. Install Python 3.10+ from https://python.org"
fi
PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_OK=$(python3 -c "import sys; print(int(sys.version_info >= (3,10)))")
if [ "$PY_OK" != "1" ]; then
    fail "Python $PY_VERSION found — need 3.10+"
fi
ok "Python $PY_VERSION"

# ── Virtual environment ─────────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
    say "Creating virtual environment .venv ..."
    python3 -m venv .venv
    ok "Virtual environment created"
else
    ok "Virtual environment already exists"
fi

# ── Activate and install ────────────────────────────────────────────────────
# shellcheck disable=SC1091
source .venv/bin/activate
say "Upgrading pip..."
pip install --quiet --upgrade pip

say "Installing Python dependencies (this takes ~1-2 min)..."
pip install --quiet -r requirements.txt
ok "Dependencies installed"

# ── Tesseract (optional — only needed for image resumes) ────────────────────
if ! command -v tesseract &>/dev/null; then
    if [[ "$OSTYPE" == "darwin"* ]] && command -v brew &>/dev/null; then
        warn "Tesseract OCR not found — needed for JPG/PNG/SVG resumes."
        read -p "Install via Homebrew? [Y/n] " -n 1 -r REPLY < /dev/tty
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            say "Installing tesseract..."
            brew install tesseract
            ok "Tesseract installed"
        else
            warn "Skipped — image resume parsing will not work, PDF still does."
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        warn "Tesseract not found. Install with: sudo apt install tesseract-ocr"
    else
        warn "Tesseract not found — only PDF resumes will work without it."
    fi
else
    ok "Tesseract already installed"
fi

# ── .env file ───────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        ok "Created .env from .env.example"
        warn "Edit .env and add your GOOGLE_API_KEY (free at https://aistudio.google.com)"
    else
        warn ".env.example not found — you'll need to create .env manually"
    fi
else
    ok ".env already exists"
fi

# ── Folders ─────────────────────────────────────────────────────────────────
mkdir -p output uploads
ok "output/ and uploads/ directories ready"

# ── Done ────────────────────────────────────────────────────────────────────
echo
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Setup complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo
echo "  Next steps:"
echo "    1.  Edit .env  →  add your GOOGLE_API_KEY (free, takes 30 sec)"
echo "        Get a key:  https://aistudio.google.com/apikey"
echo
echo "    2.  Run the app:"
echo "          source .venv/bin/activate"
echo "          streamlit run app.py"
echo
echo "    3.  Open  http://localhost:8501  in your browser"
echo
