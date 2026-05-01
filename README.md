# 🎓 Scholar-Bot

> **AI-powered resume optimizer, LinkedIn job matcher, and auto-apply agent.**
>
> Upload your resume → AI extracts your skills → scrapes LinkedIn for matching jobs → rewrites your resume for each job's ATS → pre-fills every Easy Apply form → you proof-read → one click submits.

---

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
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | **Yes** |
| LinkedIn email + password | Your LinkedIn account | Only for Auto Apply |

---

## Clone & Setup

### 1. Clone the repository

```bash
git clone https://github.com/Singhniku/scholar-bot.git
cd scholar-bot
```

### 2. Create a virtual environment (recommended)

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

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
# Required
ANTHROPIC_API_KEY=sk-ant-api03-...

# Required only for Auto Apply
LINKEDIN_EMAIL=you@example.com
LINKEDIN_PASSWORD=yourpassword

# Optional tuning
DEFAULT_LOCATION=United States
DEFAULT_NUM_JOBS=50
JOB_SEARCH_DAYS=30       # 1, 7, or 30
OUTPUT_DIR=./output
```

> **Security note:** `.env` is in `.gitignore` and will never be committed. Never put real credentials in `.env.example`.

---

## Running the App

### Web UI (recommended)

```bash
streamlit run app.py
```

Opens at **http://localhost:8501**

To run on a specific port or expose on your network:

```bash
streamlit run app.py --server.port 8080 --server.address 0.0.0.0
```

### Headless server (no browser auto-open)

```bash
streamlit run app.py --server.headless true
```

---

## CLI Usage

The CLI is useful for scripting or batch processing without the UI.

```bash
# Full pipeline: parse → match → optimise → generate outputs
python main.py \
  --resume /path/to/resume.pdf \
  --location "San Francisco, CA" \
  --jobs 50 \
  --days 7 \
  --optimize-top 3 \
  --output-dir ./output

# Resume analysis only (no LinkedIn scraping)
python main.py --resume resume.jpg --no-linkedin
```

### CLI arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--resume` | *(required)* | Path to resume file |
| `--location` | `United States` | LinkedIn job search location |
| `--jobs` | `50` | Max jobs to fetch |
| `--days` | `30` | Recency filter: `1`, `7`, or `30` |
| `--optimize-top` | `3` | Generate optimised resume for top N jobs |
| `--output-dir` | `./output` | Where to save PDFs, reports, JSON |
| `--no-linkedin` | off | Skip scraping, only analyse resume |

### CLI outputs

```
output/
├── 20260501_120000_1_SoftwareEngineer_Google.pdf     ← ATS-optimised resume
├── 20260501_120000_1_SoftwareEngineer_Google.md      ← Markdown version
├── 20260501_120000_2_DataEngineer_Meta.pdf
├── 20260501_120000_2_DataEngineer_Meta.md
├── 20260501_120000_3_MLEngineer_OpenAI.pdf
├── 20260501_120000_3_MLEngineer_OpenAI.md
├── 20260501_120000_job_report.md                     ← Full ranked job list
└── 20260501_120000_analysis.json                     ← Machine-readable snapshot
```

---

## How Each Module Works

### `src/resume_parser.py` — ResumeParser

Detects file extension and routes to the correct parser:

- **PDF** → `pdfplumber` extracts text layer + tables. Falls back to OCR via `pdf2image` + `pytesseract` if no text layer is found (scanned documents).
- **JPG / JPEG / PNG** → Loads with `Pillow`, applies sharpening + contrast enhancement, then runs `pytesseract` with `--oem 3 --psm 6` (assumes uniform text block).
- **SVG** → `cairosvg` renders to a 300 DPI PNG in memory, then same OCR path as images.

### `src/skills_extractor.py` — SkillsExtractor

Uses the Anthropic SDK with `cache_control: ephemeral` on the system prompt to reduce repeated token costs.

- **`extract_from_resume(text)`** — Sends the raw resume text to Claude with a structured JSON schema prompt. Returns name, contact, skills by category, experience list, education, projects.
- **`extract_from_job(description, title)`** — Extracts required skills, preferred skills, ATS keywords, seniority level from a job description.
- **`calculate_match_score(resume_data, job_requirements)`** — Pure Python weighted scoring:
  - Required skills matched: **70 points**
  - Preferred skills matched: **20 points**
  - ATS keyword coverage: **10 points**
  - Experience gap bonus: **up to 10 points**
  - Capped at 100.

### `src/linkedin_scraper.py` — LinkedInScraper

Scrapes LinkedIn's public `/jobs/search/` endpoint without authentication.

1. **Session warmup** — Hits `linkedin.com` to receive cookies before the search.
2. **Paginated search** — Fetches up to `num_jobs` results in pages of 25, with `sortBy=DD` (date descending) and a `f_TPR` time filter.
3. **Card parsing** — Extracts title, company, location, date, URL from `<li class="job-search-card">` elements. Falls back to JSON-LD structured data (`<script type="application/ld+json">`).
4. **Job enrichment** — Fetches the full job description from each job's individual page (limited to top 20 to stay within rate limits).
5. **Relative date parsing** — Converts "2 days ago", "1 week ago" etc. to absolute `datetime` objects.

> LinkedIn periodically changes its HTML. If scraping breaks, CSS selectors in `_SEL` and `_parse_card()` are the first place to update.

### `src/ats_optimizer.py` — ATSOptimizer

Sends resume JSON + job requirements JSON + match gap analysis to Claude AI with a strict prompt that:

- Forbids adding skills the candidate does not have
- Rewrites bullet points to mirror exact job keywords
- Adds missing ATS keywords where they truthfully apply
- Rewrites the summary to be keyword-dense and ATS-friendly
- Returns `optimization_notes` (list of changes made) and `added_keywords`

`bulk_optimize()` runs this for the top N jobs (default 3) and returns a list of `{job, optimized_resume, match_score}`.

### `src/resume_generator.py` — ResumeGenerator

Generates ATS-safe output using `reportlab`:

- **PDF** — No tables, no images, no text boxes. Clean linear flow: Name → Contact → Summary → Skills → Experience → Projects → Education → Certifications. Uses `Helvetica` (universally readable by ATS parsers). Accent colour `#1e3a5f` for section headers.
- **Markdown** — Plain Markdown version for easy editing or GitHub display.
- **Job report** — Ranked Markdown file with match scores, dates, apply links, skills gaps.

### `src/auto_apply.py` — AutoApply

A Selenium-based LinkedIn Easy Apply bot designed to run in a background thread alongside Streamlit.

**Key design decisions:**
- `on_status(job_id, status, screenshot_b64)` callback allows the Streamlit UI to poll state without blocking.
- `signal_submit(approve: bool)` + `threading.Event` creates a clean human-in-the-loop gate — the bot fills forms, takes a screenshot, then *blocks* until the user clicks Submit or Skip in the UI.
- Anti-detection: `--disable-blink-features=AutomationControlled`, removes `navigator.webdriver`, uses realistic `User-Agent`.
- Form filling uses label inference (`_infer_value`) to map field labels like "First Name", "Years of Experience", "City" to the correct resume data fields.
- Radio button logic: auto-answers work authorisation questions (Yes) and sponsorship questions (No).

---

## Auto-Apply Flow

```
User clicks "Start Auto Apply"
        │
        ▼
Background thread: AutoApply.apply_to_jobs(queue)
        │
        ├─ Login to LinkedIn (email + password)
        │
        └─ For each job in queue:
               │
               ├─ Navigate to job URL
               ├─ Click "Easy Apply" button
               ├─ Fill Step 1: contact info, phone, location
               ├─ Fill Step 2: work experience, years
               ├─ Fill Step 3: upload PDF resume
               ├─ Fill Step N: answer custom questions
               │    (radio buttons, selects, free text)
               │
               ├─ Take full-page screenshot
               │
               ├─ STATUS → waiting_approval
               │    (thread blocks on threading.Event)
               │
               │   ┌─────────────────────────────────────┐
               │   │     Streamlit UI shows screenshot    │
               │   │   [✅ Submit]     [⏭ Skip]          │
               │   └────────────┬──────────┬─────────────┘
               │                │          │
               │           approve=True  approve=False
               │                │          │
               ├────────────────┘          └─ dismiss modal
               │
               ├─ Click "Submit application"
               └─ STATUS → done
```

---

## ATS Optimisation Logic

Modern ATS (Applicant Tracking Systems) like Workday, Taleo, Greenhouse, Lever rank resumes by:

1. **Keyword density** — exact matches to job description terms
2. **Section recognition** — standard headers (EXPERIENCE, EDUCATION, SKILLS)
3. **Parse-ability** — plain text, no tables, no columns, no images
4. **Chronological ordering** — most recent experience first

Scholar-Bot addresses all four:

| ATS Factor | How Scholar-Bot handles it |
|-----------|---------------------------|
| Keywords | Claude mirrors exact phrasing from JD into bullets + summary |
| Section headers | ALL CAPS standard headers, linear PDF flow |
| Parse-ability | reportlab generates single-column, image-free PDF |
| Ordering | Experience sorted by duration field as provided |
| Missing skills | Claude adds keywords where truthfully applicable |

---

## Project Stats

| Metric | Value |
|--------|-------|
| Total Python lines | 2,522 |
| Source modules | 7 (+ app.py + main.py + config.py) |
| UI tabs | 5 |
| Supported resume formats | 5 (PDF, JPG, JPEG, PNG, SVG) |
| AI model | `claude-sonnet-4-6` |
| Prompt cache | Yes (ephemeral, system prompt) |
| Output formats | PDF, Markdown, JSON, CSV |
| Python version tested | 3.14.3 |

### Dependencies

| Package | Version | Category |
|---------|---------|----------|
| anthropic | 0.97.0 | AI / LLM |
| streamlit | 1.57.0 | Web UI |
| selenium | 4.43.0 | Browser automation |
| webdriver-manager | 4.0.2 | Browser automation |
| pdfplumber | 0.11.9 | Resume parsing |
| pytesseract | 0.3.13 | OCR |
| Pillow | 12.2.0 | Image processing |
| CairoSVG | 2.9.0 | SVG rendering |
| beautifulsoup4 | 4.14.3 | Web scraping |
| requests | 2.33.1 | HTTP |
| lxml | 6.1.0 | HTML parser |
| reportlab | 4.5.0 | PDF generation |
| python-dateutil | 2.9.0 | Date parsing |
| pandas | 3.0.2 | Data / CSV |
| python-dotenv | 1.0.1 | Config |

---

## Limitations & Known Issues

| Issue | Detail |
|-------|--------|
| LinkedIn rate limiting | LinkedIn may return empty results if too many requests are made in a short window. Wait 5–10 minutes and try again. |
| Easy Apply only | Auto Apply only works on jobs with LinkedIn's "Easy Apply" button. External application sites are not supported. |
| CAPTCHA / 2FA | If LinkedIn shows a CAPTCHA or 2FA prompt during login, the bot cannot proceed. Solve it manually in the browser window (set `headless=False`). |
| Tesseract accuracy | OCR accuracy depends on scan quality. Use a 300 DPI or higher scan for best results. |
| SVG support | Only text-based SVG resumes work well. SVGs with embedded raster images may produce poor OCR output. |
| LinkedIn HTML changes | LinkedIn periodically updates its HTML structure. If scraping stops working, update the CSS selectors in `_SEL` (linkedin_scraper.py line 25). |

---

## Roadmap

- [ ] Support for Indeed, Glassdoor, and Naukri job portals
- [ ] Cover letter generation per job (Claude AI)
- [ ] Application tracking dashboard with status history
- [ ] Email alerts for new high-match jobs
- [ ] Resume version history and diff view
- [ ] Support for `.docx` resume input
- [ ] Docker image for one-command deployment
- [ ] Multi-language resume support

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Author

Built with Claude AI (Anthropic) · [Scholar-Bot on GitHub](https://github.com/Singhniku/scholar-bot)
