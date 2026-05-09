# 🎓 Scholar-Bot

> **AI-powered resume optimizer, LinkedIn job matcher, and auto-apply agent.**
>
> Upload your resume → AI extracts your skills → scrapes LinkedIn for matching jobs → rewrites your resume for each job's ATS → pre-fills every Easy Apply form → you proof-read → one click submits.

---

<<<<<<< HEAD
## Table of Contents

1. [Demo](#demo)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Project Structure](#project-structure)
5. [Tech Stack](#tech-stack)
6. [Prerequisites](#prerequisites)
7. [Clone & Setup](#clone--setup)
8. [Configuration](#configuration)
9. [Running the App](#running-the-app)
10. [CLI Usage](#cli-usage)
11. [How Each Module Works](#how-each-module-works)
12. [Auto-Apply Flow](#auto-apply-flow)
13. [ATS Optimisation Logic](#ats-optimisation-logic)
14. [Project Stats](#project-stats)
15. [Limitations & Known Issues](#limitations--known-issues)
16. [Roadmap](#roadmap)

---

## Demo

```
streamlit run app.py
```

Open **http://localhost:8501** and use the five-tab interface:

| Tab | What it does |
|-----|-------------|
| 📄 Upload Resume | Parse resume → extract skills with Claude AI |
| 💼 Job Matches | Browse LinkedIn jobs ranked by match score + date |
| ✏️ Optimized Resumes | Download ATS-tailored PDF / Markdown resume per job |
| 🚀 Auto Apply | Bot fills LinkedIn Easy Apply → you review → submit |
| 📊 Report | Full ranked table, score distribution chart, CSV export |

---

## Features

- **Multi-format resume parsing** — PDF (native text + OCR fallback), JPG, JPEG, PNG, SVG
- **AI skill extraction** — Claude AI reads the resume and returns structured JSON (skills, experience, education, projects)
- **LinkedIn job scraping** — Searches public LinkedIn Jobs without requiring an API key; fetches full job descriptions
- **Match scoring** — Weighted algorithm (required skills 70 %, preferred 20 %, ATS keywords 10 %) against your resume
- **ATS resume rewriting** — Claude rewrites every bullet point and the summary to mirror the job's exact keywords, without fabricating experience
- **PDF + Markdown output** — Professional `reportlab`-generated PDF with proper ATS formatting (no tables, no images, clean section headers)
- **Auto Apply with human gate** — Selenium fills every Easy Apply form field, pauses before submit, shows a screenshot for review, only submits on your explicit approval
- **Chronological job ranking** — Jobs sorted by posting date (newest first), with match score as tiebreaker
- **Full report + CSV export** — Score distribution chart, ranked table, one-click CSV download

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Streamlit UI (app.py)                        │
│  Tab 1        Tab 2        Tab 3        Tab 4        Tab 5          │
│  Upload     Job Matches  Opt.Resume  Auto Apply    Report           │
└────┬────────────┬────────────┬────────────┬────────────┬────────────┘
     │            │            │            │            │
     ▼            ▼            ▼            ▼            ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ Resume   │ │LinkedIn  │ │ ATS      │ │ Auto     │ │ Resume   │
│ Parser   │ │ Scraper  │ │Optimizer │ │ Apply    │ │Generator │
└────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
     │            │            │            │            │
     │            │            │            │            │
     ▼            ▼            ▼            │            ▼
┌──────────────────────────────────────┐   │      ┌──────────┐
│         Skills Extractor             │   │      │reportlab │
│   (Claude AI — anthropic SDK)        │   │      │  PDF     │
└──────────────────────────────────────┘   │      └──────────┘
                                           │
                                     ┌─────▼──────┐
                                     │  Selenium  │
                                     │  Chrome    │
                                     │  Driver    │
                                     └────────────┘
```

### Data flow

```
Resume file
    │
    ▼
ResumeParser          ← pdfplumber / pytesseract / cairosvg
    │ raw text
    ▼
SkillsExtractor       ← Claude AI (claude-sonnet-4-6)
    │ structured JSON {skills, experience, education …}
    ▼
LinkedInScraper       ← requests + BeautifulSoup
    │ list of job dicts {title, company, date, description, url}
    ▼
SkillsExtractor       ← Claude AI (per job)
    │ {required_skills, ats_keywords, match_score}
    ▼
ATSOptimizer          ← Claude AI
    │ rewritten resume JSON (per top-N jobs)
    ▼
ResumeGenerator       ← reportlab PDF + Markdown
    │ .pdf + .md files
    ▼
AutoApply             ← Selenium + webdriver-manager
    │ pre-filled Easy Apply form + screenshot
    ▼
Human review (Streamlit) → Submit / Skip
```

---

## Project Structure

```
scholar-bot/
│
├── app.py                  # Streamlit web UI — 5 tabs, full pipeline
├── main.py                 # CLI entry point (alternative to UI)
├── config.py               # Env-based configuration constants
│
├── src/
│   ├── __init__.py
│   ├── resume_parser.py    # PDF/image/SVG → plain text
│   ├── skills_extractor.py # Claude AI: extract skills + score jobs
│   ├── linkedin_scraper.py # Scrape LinkedIn public job search
│   ├── ats_optimizer.py    # Claude AI: rewrite resume for each job
│   ├── resume_generator.py # reportlab PDF + Markdown output
│   └── auto_apply.py       # Selenium LinkedIn Easy Apply bot
│
├── output/                 # Generated PDFs, Markdown, reports (gitignored)
├── uploads/                # Temp upload directory (gitignored)
│
├── requirements.txt        # All Python dependencies
├── .env                    # Your secrets — NEVER commit (gitignored)
├── .env.example            # Template — safe to commit
└── .gitignore
```

---

## Tech Stack

### AI / LLM

| Library | Version | Used For |
|---------|---------|----------|
| `anthropic` | 0.97.0 | Claude AI API — skill extraction, job analysis, resume rewriting |
| Model | `claude-sonnet-4-6` | All AI inference tasks |
| Prompt caching | `cache_control: ephemeral` | Reduces token cost on repeated calls |

### Resume Parsing

| Library | Version | Used For |
|---------|---------|----------|
| `pdfplumber` | 0.11.9 | Native PDF text + table extraction |
| `pytesseract` | 0.3.13 | OCR for JPG/PNG/SVG and scanned PDFs |
| `Pillow` | 12.2.0 | Image preprocessing before OCR (sharpen, contrast) |
| `cairosvg` | 2.9.0 | SVG → PNG conversion before OCR |

### Web Scraping

| Library | Version | Used For |
|---------|---------|----------|
| `requests` | 2.33.1 | HTTP requests to LinkedIn public search |
| `beautifulsoup4` | 4.14.3 | HTML parsing of job cards and descriptions |
| `lxml` | 6.1.0 | Fast HTML/XML parser backend for BeautifulSoup |
| `python-dateutil` | 2.9.0 | Parse relative dates ("2 days ago") and ISO dates |

### Browser Automation (Auto Apply)

| Library | Version | Used For |
|---------|---------|----------|
| `selenium` | 4.43.0 | Chrome automation for LinkedIn Easy Apply |
| `webdriver-manager` | 4.0.2 | Auto-downloads matching ChromeDriver |
| `threading` | stdlib | Run Selenium in background while Streamlit UI stays live |

### Output Generation

| Library | Version | Used For |
|---------|---------|----------|
| `reportlab` | 4.5.0 | Generate ATS-safe PDF resumes |
| `pandas` | 3.0.2 | Job report tables + CSV export |

### Web UI

| Library | Version | Used For |
|---------|---------|----------|
| `streamlit` | 1.57.0 | Full-stack web UI, file upload, progress, downloads |

---

## Prerequisites

### System requirements

| Requirement | Minimum | Notes |
|------------|---------|-------|
| Python | 3.10+ | Tested on 3.14 |
| Google Chrome | Any recent | Required for Auto Apply |
| Tesseract OCR | 4.x+ | Required for image/SVG resume parsing |
| macOS / Linux / Windows | — | All supported |

### API keys

| Key | Where to get it | Required? |
|-----|----------------|-----------|
| `GOOGLE_API_KEY` | [aistudio.google.com](https://aistudio.google.com) | Recommended (free tier) |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | Alternative to Gemini |
| `LINKEDIN_PROFILE_URL` | Your public LinkedIn profile URL | Optional — shown on resume + pre-fills Easy Apply forms |
| `LINKEDIN_EMAIL` + `LINKEDIN_PASSWORD` | Your LinkedIn account | Optional — **only** needed to enable the Auto Apply tab |

> Scholar-Bot runs end-to-end (resume parsing, job search, match scoring, ATS optimisation, PDF download) with just an AI key. Your LinkedIn password is **not** required unless you specifically want the bot to submit Easy Apply forms for you.

---

## Clone & Setup

### 1. Clone the repository
=======
## ⚡ Quick Start (3 commands)
>>>>>>> 2cdd351 (docs: add one-command setup.sh + simplified README quick-start)

```bash
git clone https://github.com/Singhniku/scholar-bot.git
cd scholar-bot
./setup.sh
```

The setup script:
- Creates a Python virtual environment (`.venv`)
- Installs all dependencies
- Offers to install Tesseract OCR (macOS via Homebrew)
- Creates `.env` from `.env.example`
- Prepares `output/` and `uploads/` folders

Then add your free Gemini API key to `.env` and start the app:

```bash
source .venv/bin/activate
<<<<<<< HEAD

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Tesseract OCR

Tesseract is needed for parsing JPG/PNG/SVG resumes and scanned PDFs.

```bash
# macOS
brew install tesseract

# Ubuntu / Debian
sudo apt update && sudo apt install tesseract-ocr

# Windows
# Download installer from https://github.com/UB-Mannheim/tesseract/wiki
# Add the install directory to PATH
```

### 5. Install Chrome (for Auto Apply)

Auto Apply uses Google Chrome. Make sure Chrome is installed.  
`webdriver-manager` automatically downloads the matching ChromeDriver — no manual setup needed.

---

## Configuration

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
# Required — at least one AI key
GOOGLE_API_KEY=...            # free at aistudio.google.com
# or
ANTHROPIC_API_KEY=sk-ant-api03-...

# Optional — appears on generated resumes and pre-fills the "LinkedIn URL"
# question on Easy Apply forms
LINKEDIN_PROFILE_URL=https://www.linkedin.com/in/your-handle

# Optional — ONLY required to enable the Auto Apply tab. The rest of the app
# (job search, matching, resume optimisation, downloads) works without these.
LINKEDIN_EMAIL=
LINKEDIN_PASSWORD=

# Optional tuning
DEFAULT_LOCATION=United States
DEFAULT_NUM_JOBS=50
JOB_SEARCH_DAYS=30
OUTPUT_DIR=./output
```

> **Security note:** `.env` is in `.gitignore` and will never be committed. Never put real credentials in `.env.example`.

---

## Running the App

### Web UI (recommended)

```bash
=======
>>>>>>> 2cdd351 (docs: add one-command setup.sh + simplified README quick-start)
streamlit run app.py
```

Open **http://localhost:8501** — done.

> 🔑 **Get a free Gemini key** at [aistudio.google.com/apikey](https://aistudio.google.com/apikey) — takes 30 seconds, no credit card.
> The free tier handles ~1500 requests/day which is more than enough.

---

## 🚀 What it does

| Tab | What it does |
|-----|-------------|
| 📄 **Upload Resume** | Parse PDF/JPG/PNG/SVG → extract skills → run ATS audit |
| 💼 **Job Matches** | Browse LinkedIn jobs ranked by match score + recency |
| ✏️ **Optimised Resumes** | Download ATS-tailored PDF / Markdown per job |
| 🚀 **Auto Apply** | Bot fills LinkedIn Easy Apply → you review → submit |
| 📊 **Report** | Full ranked table, score chart, CSV export |

---

## ✨ Features

- **Multi-format resume parsing** — PDF (native + OCR fallback), JPG, JPEG, PNG, SVG
- **Dual AI provider** — Google Gemini (free, default) or Anthropic Claude (paid)
- **Keyword-only fallback mode** — fully usable when AI quota is exhausted
- **LinkedIn job scraping** — searches public LinkedIn Jobs without an account
- **Job-title search + match-% filter** — only shows jobs ≥ your chosen threshold
- **ATS audit** — 7-rule keyword score + AI-powered bullet rewrites and gap analysis
- **Resume optimisation** — bullets rewritten to mirror each job's exact keywords (no fabrication)
- **Before/after ATS score** — see exactly how much the optimisation improved your score
- **Auto Apply with human gate** — Selenium fills every form, pauses for your approval, only submits on click
- **PDF + Markdown output** — single-column ATS-safe formatting, no images, no tables

---

## 📋 Prerequisites

| Requirement | Minimum | Required for |
|-------------|---------|--------------|
| Python | 3.10+ | Everything |
| Google Chrome | Recent | Auto Apply only |
| Tesseract OCR | 4.x+ | Image / SVG resume parsing only — PDFs work without it |

`./setup.sh` checks all of these and offers to install Tesseract on macOS.

### API keys

- **Google Gemini** (recommended, free) — [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- **Anthropic Claude** (optional, paid) — [console.anthropic.com](https://console.anthropic.com)

Set in `.env`:

```dotenv
AI_PROVIDER=gemini                    # or "anthropic"
GOOGLE_API_KEY=AIza...                # required for AI mode
ANTHROPIC_API_KEY=                    # only if AI_PROVIDER=anthropic

# Optional — only needed for Auto Apply
LINKEDIN_EMAIL=you@example.com
LINKEDIN_PASSWORD=yourpassword
```

> Without an AI key the app still works in **keyword mode** — jobs are still fetched, scored, and you can download a basic optimised resume.

---

## 🔧 Manual setup (alternative to `setup.sh`)

```bash
git clone https://github.com/Singhniku/scholar-bot.git
cd scholar-bot
python3 -m venv .venv
source .venv/bin/activate                 # Linux/macOS
# .venv\Scripts\Activate.ps1              # Windows PowerShell
pip install -r requirements.txt
cp .env.example .env                       # then edit .env
streamlit run app.py
```

Tesseract by platform:
```bash
# macOS
brew install tesseract
# Ubuntu / Debian
sudo apt install tesseract-ocr
# Windows: download installer from https://github.com/UB-Mannheim/tesseract/wiki
```

---

## 🏗️ Architecture

```
Resume file (PDF/JPG/PNG/SVG)
    │
    ▼
ResumeParser              ← pdfplumber / pytesseract / cairosvg
    │ raw text
    ▼
SkillsExtractor           ← Gemini or Claude  (fallback: regex parser)
    │ structured JSON {skills, experience, education …}
    ▼
LinkedInScraper           ← requests + BeautifulSoup
    │ job dicts {title, company, date, description, url}
    ▼
score_match               ← keyword overlap + ATS keyword scoring
    │ {match_score, matched, missing}
    ▼
ATSOptimizer              ← Gemini or Claude (per job)
    │ rewritten resume JSON
    ▼
ResumeGenerator           ← reportlab PDF + Markdown
    │ files
    ▼
AutoApply                 ← Selenium (Easy Apply forms)
    │ pre-filled form + screenshot
    ▼
Human review (Streamlit)  ─→ Submit / Skip
```

---

## 📁 Project Structure

```
scholar-bot/
├── app.py                    Streamlit web UI — 5 tabs, full pipeline
├── main.py                   CLI entry point (alternative to UI)
├── config.py                 Environment-based configuration
├── setup.sh                  One-command setup script
├── test_e2e.py               End-to-end test suite
├── requirements.txt          All Python dependencies
├── .env.example              Config template — copy to .env
│
├── src/
│   ├── ai_client.py          Unified Gemini/Anthropic client
│   ├── resume_parser.py      PDF / image / SVG → text
│   ├── skills_extractor.py   AI: structured skill extraction + scoring
│   ├── fallback_extractor.py Regex-based extraction (no AI)
│   ├── linkedin_scraper.py   LinkedIn public-jobs scraper
│   ├── ats_optimizer.py      AI: rewrite resume per job
│   ├── resume_generator.py   reportlab PDF + Markdown
│   └── auto_apply.py         Selenium Easy Apply bot
│
├── skills/                   Reusable test fixtures + 50+ unit tests
└── output/  uploads/         Generated files (gitignored)
```

---

## 🧪 Testing

```bash
source .venv/bin/activate

# Full unit test suite (mocked AI — no network, no API key needed)
pytest skills/ -v

# End-to-end live test (uses your real API key + LinkedIn)
python test_e2e.py
```

`test_e2e.py` runs all 9 scenarios: fallback extraction, AI extraction, ATS audit, LinkedIn search (with/without title), scoring, PDF generation, AI optimisation, edge cases.

---

## 🤖 Auto-Apply Flow

```
User clicks "Start Auto Apply"
        │
        ▼
Background thread fills each Easy Apply form
        │
        ▼
Bot pauses, takes a screenshot, shows it in UI
        │
        ▼
User reviews → clicks ✅ Submit  or  ⏭ Skip
        │
        ▼
Bot submits / dismisses, moves to next job
```

The bot **never submits without your explicit approval** — `threading.Event` blocks until you click.

---

## 📊 ATS Optimisation Logic

| ATS factor | How Scholar-Bot handles it |
|-----------|---------------------------|
| Keyword density | AI mirrors exact phrasing from JD into bullets + summary |
| Section headers | Standard ALL-CAPS headers, linear PDF flow |
| Parse-ability | reportlab generates single-column, image-free PDF |
| Ordering | Experience sorted by date, most recent first |
| Missing skills | AI adds keywords only where truthfully applicable |

The before/after ATS score (shown in the Optimised Resumes section) is computed from a 7-rule keyword audit:

| Check | Points |
|-------|--------|
| Contact info (name + email + phone) | 20 |
| Professional summary | 15 |
| Skills section | 15 |
| Work experience with bullets | 20 |
| Education | 10 |
| 10+ technical keywords | 10 |
| Word count 400-1200 | 10 |

---

## 🛠️ Tech Stack

| Layer | Library |
|-------|---------|
| AI / LLM | `google-genai`, `anthropic` |
| Resume parsing | `pdfplumber`, `pytesseract`, `Pillow`, `cairosvg` |
| Scraping | `requests`, `beautifulsoup4`, `lxml`, `python-dateutil` |
| Browser automation | `selenium`, `webdriver-manager` |
| Output | `reportlab` (PDF), `pandas` (CSV) |
| UI | `streamlit` |

---

## ⚠️ Limitations

- **LinkedIn rate limiting** — too many requests in a short window returns empty results. Wait 5–10 min.
- **Easy Apply only** — Auto Apply works on jobs with LinkedIn's "Easy Apply" button. External application sites are skipped.
- **CAPTCHA / 2FA** — if LinkedIn challenges you, run with `headless=False` and solve manually.
- **OCR quality** — depends on scan quality; use 300 DPI+ for best results on image resumes.
- **HTML changes** — LinkedIn updates its markup occasionally; if scraping breaks, update selectors in `src/linkedin_scraper.py`.

---

## 🗺️ Roadmap

- [ ] Indeed / Glassdoor / Naukri scraping
- [ ] AI-generated cover letter per job
- [ ] Application tracking dashboard
- [ ] `.docx` resume input
- [ ] Docker image
- [ ] Multi-language resume support

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

**Built with Claude AI** · [scholar-bot on GitHub](https://github.com/Singhniku/scholar-bot)
