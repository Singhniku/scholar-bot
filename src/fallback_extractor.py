"""
Keyword + structure-based resume and job extractor — no AI required.

Parses real resume text using regex/heuristics:
  • name, email, phone, location, linkedin
  • current title + experience entries (company, title, duration, bullets)
  • education entries (degree, institution, year, GPA)
  • categorised skills (technical / soft / tools / frameworks)
  • calculated years of experience from date ranges
  • clean professional summary built from extracted data

Used when AI quota is exhausted or no API key is set.
"""
from __future__ import annotations
import re
from datetime import datetime
from typing import Any

# ── Common tech keywords ──────────────────────────────────────────────────────
_TECH = {
    # Languages
    "python","java","javascript","typescript","go","golang","rust","c++","c#","ruby",
    "php","swift","kotlin","scala","r","matlab","bash","shell","sql","html","css",
    # Frameworks / libs
    "react","angular","vue","django","flask","fastapi","spring","spring boot","nodejs","express",
    "tensorflow","pytorch","keras","sklearn","scikit-learn","pandas","numpy",
    "nextjs","nuxtjs","laravel","rails","graphql","grpc","rest","restful","hibernate",
    # Cloud / infra
    "aws","gcp","azure","docker","kubernetes","k8s","terraform","ansible","jenkins",
    "github actions","circleci","gitlab","ci/cd","devops","mlops","linux","unix",
    # Data
    "spark","kafka","airflow","dbt","snowflake","redshift","bigquery","postgresql","postgres",
    "mysql","mongodb","redis","elasticsearch","dynamodb","cassandra","sqlite","rabbitmq",
    # AI / ML
    "agentic ai","genai","llm","llms","rag","vector database","vector databases",
    # Tools
    "git","jira","confluence","slack","figma","postman","grafana","prometheus",
    "mcp","quartz scheduler",
    # Soft / roles
    "agile","scrum","leadership","communication","mentoring","problem solving",
}

_SOFT_SET     = {"agile","scrum","leadership","communication","mentoring","problem solving"}
_FRAMEWORK_SET= {"spring","spring boot","django","flask","fastapi","react","angular",
                 "vue","nextjs","nuxtjs","laravel","rails","express","hibernate"}
_TOOL_SET     = {"git","jira","confluence","docker","kubernetes","jenkins","postman",
                 "grafana","prometheus","aws","gcp","azure","mcp","quartz scheduler"}

# ── Regex patterns ────────────────────────────────────────────────────────────
_EXP_RE       = re.compile(r"(\d+)\+?\s*(?:years?|yrs?)(?:\s+of)?\s+(?:experience|exp)", re.I)
_EMAIL_RE     = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE     = re.compile(r"(?<!\w)(\+?\d{1,3}[\s\-]?)?\(?\d{3,5}\)?[\s\-]?\d{3,5}[\s\-]?\d{3,5}(?!\w)")
_LINKEDIN_RE  = re.compile(r"linkedin\.com/in/[a-zA-Z0-9\-_]+", re.I)

_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
_DATE_RANGE_RE = re.compile(
    rf"({_MONTH}\s+\d{{4}}|\d{{4}})\s*[–\-—to]+\s*({_MONTH}\s+\d{{4}}|\d{{4}}|Present|Current)",
    re.I,
)

_SECTION_RE = re.compile(
    r"^\s*(PROFESSIONAL EXPERIENCE|WORK EXPERIENCE|EXPERIENCE|EDUCATION|"
    r"TECHNICAL SKILLS|SKILLS|PROJECTS|CERTIFICATIONS|LEADERSHIP EXPERIENCE|"
    r"SUMMARY|OBJECTIVE|PROFILE|ACHIEVEMENTS)\s*:?\s*$",
    re.I | re.M,
)

_GPA_RE     = re.compile(r"GPA\s*[:\-]?\s*([\d.]+)", re.I)
_PERCENT_RE = re.compile(r"(\d{1,2}\.?\d{0,2})\s*%")
_YEAR_RE    = re.compile(r"(?:19|20)\d{2}")
_DEGREE_RE  = re.compile(
    r"(B\.?Tech|B\.?E\.?|B\.?S\.?|M\.?Tech|M\.?E\.?|M\.?S\.?|MBA|Ph\.?D|"
    r"Bachelor[a-z]*|Master[a-z]*|Diploma|Intermediate|Doctorate)[^.\n]*",
    re.I,
)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _split_sections(text: str) -> dict[str, str]:
    """Split resume by uppercase section headers."""
    sections: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        return {"_full": text, "_preamble": text}
    for i, m in enumerate(matches):
        name = m.group(1).upper().strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[name] = text[start:end].strip()
    sections["_preamble"] = text[:matches[0].start()].strip()
    return sections


def _extract_location(preamble: str) -> str:
    for line in preamble.split("\n"):
        line = line.strip()
        if not line or _EMAIL_RE.search(line) or "linkedin" in line.lower():
            continue
        m = re.search(
            r"([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?),\s*([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?)",
            line)
        if m:
            return f"{m.group(1)}, {m.group(2)}"
    return ""


def _calc_years_experience(exp_section: str) -> int:
    if not exp_section:
        return 0
    total_months = 0
    now = datetime.now()
    month_idx = {m: i for i, m in enumerate(
        ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"], start=1)}

    def parse_date(s: str):
        s = s.strip().lower()
        if s in ("present", "current"):
            return now
        m = re.match(rf"({_MONTH})\s+(\d{{4}})", s, re.I)
        if m:
            mi = month_idx.get(m.group(1).lower()[:3], 1)
            return datetime(int(m.group(2)), mi, 1)
        m = re.match(r"(\d{4})", s)
        if m:
            return datetime(int(m.group(1)), 1, 1)
        return None

    for m in _DATE_RANGE_RE.finditer(exp_section):
        start, end = parse_date(m.group(1)), parse_date(m.group(2))
        if start and end and end > start:
            total_months += (end.year - start.year) * 12 + (end.month - start.month)
    return max(0, round(total_months / 12))


def _parse_experience(exp_section: str) -> list[dict[str, Any]]:
    if not exp_section:
        return []
    lines = [ln.rstrip() for ln in exp_section.split("\n")]
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        bullet = line.startswith(("•","-","*","◦","▪","·"))
        date_m = _DATE_RANGE_RE.search(line)

        if not bullet and date_m:
            if current:
                entries.append(current)
            company = _DATE_RANGE_RE.sub("", line).strip(" \t–-—|")
            current = {
                "title":    "",
                "company":  company,
                "duration": date_m.group(0),
                "achievements": [],
                "location": "",
            }
        elif current is not None and bullet:
            current["achievements"].append(line.lstrip("•-*◦▪· ").strip())
        elif current is not None and not current["title"]:
            parts = re.split(r"\s{2,}|\t+", line, maxsplit=1)
            current["title"] = parts[0].strip()
            if len(parts) > 1:
                current["location"] = parts[1].strip()

    if current:
        entries.append(current)
    # Keep only entries that have at least a company or a title
    return [e for e in entries if e.get("company") or e.get("title")]


def _parse_education(edu_section: str) -> list[dict[str, Any]]:
    if not edu_section:
        return []
    blocks = [b.strip() for b in re.split(r"\n\s*\n", edu_section) if b.strip()]
    if not blocks:
        blocks = [edu_section.strip()]

    entries: list[dict[str, Any]] = []
    for block in blocks:
        text = block.replace("\n", " ")
        first_line = block.split("\n")[0].strip()
        first_line = re.sub(r"\s+GPA.*$", "", first_line, flags=re.I).strip()
        first_line = re.sub(r"\s+\d{1,2}\.?\d{0,2}%$", "", first_line).strip()
        institution = first_line

        deg_m = _DEGREE_RE.search(text)
        degree = deg_m.group(0).strip().rstrip(",") if deg_m else ""

        years_found = _YEAR_RE.findall(text)
        year = ""
        if len(years_found) >= 2:
            year = f"{years_found[0]} – {years_found[-1]}"
        elif years_found:
            year = years_found[0]

        gpa = ""
        gpa_m = _GPA_RE.search(text)
        if gpa_m:
            gpa = f"GPA {gpa_m.group(1)}"
        else:
            pct_m = _PERCENT_RE.search(text)
            if pct_m:
                gpa = f"{pct_m.group(1)}%"

        if institution or degree:
            entries.append({
                "institution": institution,
                "degree":      degree,
                "year":        year,
                "gpa":         gpa,
            })
    return entries


def _parse_skills(skills_section: str) -> dict[str, list[str]]:
    """
    Parse 'Languages: x, y' or 'Languages & Frameworks: a, b' style blocks.
    When the category mentions both languages and frameworks, items are
    re-classified per-item using the framework set so 'Python' goes to
    technical and 'Spring Boot' goes to frameworks.
    """
    found: dict[str, list[str]] = {"technical": [], "tools": [], "frameworks": [], "languages": []}
    if not skills_section:
        return found
    for line in skills_section.split("\n"):
        line = line.strip()
        if ":" not in line:
            continue
        category, items = line.split(":", 1)
        skills  = [s.strip() for s in re.split(r"[,;]", items) if s.strip()]
        cat_low = category.lower()
        has_lang = "language" in cat_low
        has_fw   = "framework" in cat_low or "library" in cat_low
        has_tool = "tool" in cat_low or "infra" in cat_low or "platform" in cat_low

        if has_lang and has_fw:
            for s in skills:
                if s.lower() in _FRAMEWORK_SET:
                    found["frameworks"].append(s)
                else:
                    found["technical"].append(s)
        elif has_fw:
            found["frameworks"].extend(skills)
        elif has_tool:
            found["tools"].extend(skills)
        elif has_lang:
            found["languages"].extend(skills)
        else:
            found["technical"].extend(skills)
    return found


def _dedupe_ci(items: list[str]) -> list[str]:
    """Deduplicate case-insensitively, preserve first occurrence's casing."""
    seen: dict[str, str] = {}
    for item in items:
        key = item.lower().strip()
        if key and key not in seen:
            seen[key] = item.strip()
    return list(seen.values())


def _build_summary(rd: dict) -> str:
    parts = []
    title = rd.get("current_title", "")
    years = rd.get("experience_years", 0)
    if title and years:
        parts.append(f"{title} with {years}+ years of experience.")
    elif title:
        parts.append(f"{title}.")
    elif years:
        parts.append(f"Software professional with {years}+ years of experience.")

    skills = (rd.get("technical_skills", []) + rd.get("frameworks", []))[:6]
    if skills:
        parts.append("Skilled in " + ", ".join(skills) + ".")

    if rd.get("experience"):
        first = rd["experience"][0]
        if first.get("achievements"):
            ach = first["achievements"][0].rstrip(".")
            if len(ach) > 30:
                parts.append(ach + ".")

    return " ".join(parts).strip()


# ── Main extractors ──────────────────────────────────────────────────────────
def extract_resume(text: str) -> dict[str, Any]:
    """Extract structured resume data using regex/heuristics — no AI."""
    if not text or not text.strip():
        return _empty_resume()

    sections = _split_sections(text)
    preamble = sections.get("_preamble", text[:600])
    exp_text = (sections.get("PROFESSIONAL EXPERIENCE")
                or sections.get("WORK EXPERIENCE")
                or sections.get("EXPERIENCE", ""))
    edu_text = sections.get("EDUCATION", "")
    skl_text = sections.get("TECHNICAL SKILLS") or sections.get("SKILLS", "")

    lower = text.lower()

    email_m = _EMAIL_RE.search(text)
    email   = email_m.group(0) if email_m else ""
    phone_m = _PHONE_RE.search(text)
    phone   = phone_m.group(0).strip() if phone_m else ""
    linkedin_m = _LINKEDIN_RE.search(text)
    linkedin   = linkedin_m.group(0) if linkedin_m else ""
    location   = _extract_location(preamble)

    # Name: first 1-4 capitalised words near top
    name = ""
    for line in preamble.split("\n"):
        line = line.strip()
        parts = line.split()
        if 1 < len(parts) <= 4 and all(p[0].isupper() for p in parts if p[0].isalpha()):
            name = line
            break

    # Skills (categorised + keyword scan)
    cat_skills = _parse_skills(skl_text)
    found_kw   = sorted(w for w in _TECH if w in lower)

    tech       = _dedupe_ci(cat_skills["technical"] + cat_skills["languages"]
                            + [s for s in found_kw
                               if s not in _SOFT_SET
                               and s not in _FRAMEWORK_SET
                               and s not in _TOOL_SET])
    frameworks = _dedupe_ci(cat_skills["frameworks"]
                            + [s for s in found_kw if s in _FRAMEWORK_SET])
    tools      = _dedupe_ci(cat_skills["tools"]
                            + [s for s in found_kw if s in _TOOL_SET])
    soft       = _dedupe_ci([s for s in found_kw if s in _SOFT_SET])

    fw_lower   = {f.lower() for f in frameworks}
    tool_lower = {t.lower() for t in tools}
    tech       = [t for t in tech
                  if t.lower() not in fw_lower and t.lower() not in tool_lower]

    experience    = _parse_experience(exp_text)
    current_title = (experience[0].get("title")
                     if experience and experience[0].get("title") else "")

    exp_match = _EXP_RE.search(text)
    years     = (int(exp_match.group(1)) if exp_match
                 else _calc_years_experience(exp_text))

    education = _parse_education(edu_text)

    rd = {
        "name":              name,
        "email":             email,
        "phone":             phone,
        "location":          location,
        "linkedin":          linkedin,
        "summary":           "",
        "experience_years":  years,
        "current_title":     current_title,
        "technical_skills":  tech,
        "soft_skills":       soft,
        "tools":             tools,
        "languages":         [],
        "frameworks":        frameworks,
        "certifications":    [],
        "education":         education,
        "experience":        experience,
        "projects":          [],
        "all_keywords":      found_kw,
        "_fallback":         True,
    }
    rd["summary"] = _build_summary(rd)
    return rd


def extract_job(description: str, title: str = "") -> dict[str, Any]:
    """Extract requirements from a job description without any AI call."""
    if not description:
        return {
            "title": title or "",
            "required_skills": [], "preferred_skills": [],
            "required_experience_years": 0,
            "education_required": "", "key_responsibilities": [],
            "ats_keywords": [], "seniority_level": "", "job_type": "",
            "_fallback": True,
        }
    lower    = description.lower()
    required = sorted(w for w in _TECH if w in lower)
    exp_match= _EXP_RE.search(description)
    exp_req  = int(exp_match.group(1)) if exp_match else 0

    return {
        "title":                     title or "",
        "required_skills":           required,
        "preferred_skills":          [],
        "required_experience_years": exp_req,
        "education_required":        "",
        "key_responsibilities":      [],
        "ats_keywords":              required[:10],
        "seniority_level":           "",
        "job_type":                  "",
        "_fallback":                 True,
    }


def score_match(resume_data: dict, job_reqs: dict) -> dict[str, Any]:
    """Simple keyword-overlap scoring — no AI."""
    resume_kw = {s.lower() for s in (resume_data.get("all_keywords", [])
                  + resume_data.get("technical_skills", [])
                  + resume_data.get("tools", [])
                  + resume_data.get("frameworks", []))}

    required = [s.lower() for s in job_reqs.get("required_skills", [])]
    ats_kws  = [s.lower() for s in job_reqs.get("ats_keywords", [])]

    matched = [s for s in required if s in resume_kw]
    missing = [s for s in required if s not in resume_kw]

    score = (len(matched) / max(len(required), 1)) * 100 if required else 0

    return {
        "score":                round(score, 1),
        "matched_required":     matched,
        "missing_required":     missing,
        "matched_preferred":    [],
        "missing_preferred":    [],
        "matched_ats_keywords": [s for s in ats_kws if s in resume_kw],
        "experience_gap":       0,
        "_fallback":            True,
    }


def _empty_resume() -> dict[str, Any]:
    return {
        "name": "", "email": "", "phone": "", "location": "", "linkedin": "",
        "summary": "", "experience_years": 0, "current_title": "",
        "technical_skills": [], "soft_skills": [], "tools": [],
        "languages": [], "frameworks": [], "certifications": [],
        "education": [], "experience": [], "projects": [],
        "all_keywords": [], "_fallback": True,
    }
