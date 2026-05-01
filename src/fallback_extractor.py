"""
Keyword-based resume and job extractor — no AI required.

Used automatically when the AI quota is exhausted or the API key is missing.
Covers ~80 % of common tech skills via regex and a curated keyword list.
"""
from __future__ import annotations
import re
from typing import Any

# ── Common tech keywords ──────────────────────────────────────────────────────
_TECH = {
    # Languages
    "python","java","javascript","typescript","go","golang","rust","c++","c#","ruby",
    "php","swift","kotlin","scala","r","matlab","bash","shell","sql","html","css",
    # Frameworks / libs
    "react","angular","vue","django","flask","fastapi","spring","nodejs","express",
    "tensorflow","pytorch","keras","sklearn","scikit-learn","pandas","numpy",
    "nextjs","nuxtjs","laravel","rails","graphql","grpc","rest","restful",
    # Cloud / infra
    "aws","gcp","azure","docker","kubernetes","k8s","terraform","ansible","jenkins",
    "github actions","circleci","gitlab","ci/cd","devops","mlops","linux","unix",
    # Data
    "spark","kafka","airflow","dbt","snowflake","redshift","bigquery","postgresql",
    "mysql","mongodb","redis","elasticsearch","dynamodb","cassandra","sqlite",
    # Tools
    "git","jira","confluence","slack","figma","postman","grafana","prometheus",
    # Soft / roles
    "agile","scrum","leadership","communication","mentoring","problem solving",
}

# Years-of-experience patterns
_EXP_RE = re.compile(
    r"(\d+)\+?\s*(?:years?|yrs?)(?:\s+of)?\s+(?:experience|exp)",
    re.IGNORECASE,
)

# Email / phone
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"[\+]?[\d\s\-\(\)]{7,15}")


def extract_resume(text: str) -> dict[str, Any]:
    """Extract structured data from raw resume text without any AI call."""
    lower = text.lower()
    words = set(re.findall(r"[a-zA-Z][a-zA-Z0-9+#.\-/]*", lower))

    # Skills: intersection of text words with our keyword list
    found_skills = sorted(w for w in _TECH if w in lower)

    tech = [s for s in found_skills if s not in {"agile","scrum","leadership",
            "communication","mentoring","problem solving"}]
    soft = [s for s in found_skills if s in {"agile","scrum","leadership",
            "communication","mentoring","problem solving"}]

    # Experience years
    exp_match = _EXP_RE.search(text)
    exp_years = int(exp_match.group(1)) if exp_match else 0

    # Contact
    email_m = _EMAIL_RE.search(text)
    phone_m = _PHONE_RE.search(text)

    # Name — first non-empty line that looks like a name (2 capitalised words)
    name = ""
    for line in text.split("\n"):
        line = line.strip()
        parts = line.split()
        if 2 <= len(parts) <= 4 and all(p[0].isupper() for p in parts if p.isalpha()):
            name = line
            break

    return {
        "name": name,
        "email": email_m.group(0) if email_m else "",
        "phone": phone_m.group(0).strip() if phone_m else "",
        "location": "",
        "summary": text[:300].replace("\n", " "),
        "experience_years": exp_years,
        "current_title": "",
        "technical_skills": tech,
        "soft_skills": soft,
        "tools": [],
        "languages": [],
        "frameworks": [],
        "certifications": [],
        "education": [],
        "experience": [],
        "projects": [],
        "all_keywords": found_skills,
        "_fallback": True,
    }


def extract_job(description: str, title: str = "") -> dict[str, Any]:
    """Extract requirements from a job description without any AI call."""
    lower = description.lower()

    required = sorted(w for w in _TECH if w in lower)

    exp_match = _EXP_RE.search(description)
    exp_req = int(exp_match.group(1)) if exp_match else 0

    return {
        "title": title,
        "required_skills": required,
        "preferred_skills": [],
        "required_experience_years": exp_req,
        "education_required": "",
        "key_responsibilities": [],
        "ats_keywords": required[:10],
        "seniority_level": "",
        "job_type": "",
        "_fallback": True,
    }


def score_match(resume_data: dict, job_reqs: dict) -> dict[str, Any]:
    """Simple keyword-overlap scoring — no AI."""
    resume_kw = {s.lower() for s in resume_data.get("all_keywords", [])
                 + resume_data.get("technical_skills", [])
                 + resume_data.get("tools", [])
                 + resume_data.get("frameworks", [])}

    required  = [s.lower() for s in job_reqs.get("required_skills", [])]
    ats_kws   = [s.lower() for s in job_reqs.get("ats_keywords", [])]

    matched = [s for s in required if s in resume_kw]
    missing = [s for s in required if s not in resume_kw]

    score = (len(matched) / max(len(required), 1)) * 100 if required else 0

    return {
        "score": round(score, 1),
        "matched_required": matched,
        "missing_required": missing,
        "matched_preferred": [],
        "missing_preferred": [],
        "matched_ats_keywords": [s for s in ats_kws if s in resume_kw],
        "experience_gap": 0,
        "_fallback": True,
    }
