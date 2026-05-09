"""
Scholar-Bot pipeline — the canonical end-to-end flow.

    parse_resume(file)            → resume_data
    extract_resume_skills(text)   → resume_data (skills/exp/edu structured)
    fetch_jobs(title, loc, ...)   → list[job]
    match_resume_to_jobs(rd, js)  → list[ScoredJob]
    filter_by_match(scored, pct)  → list[ScoredJob]
    upgrade_cv(rd, job, ...)      → optimized resume_data
    run_full_pipeline(...)        → PipelineResult

This module has no Streamlit / UI dependency. It is the layer the UI calls
into, and it's also what test_e2e.py exercises. Keeping it isolated means
the same logic can be reused from a CLI, a test, or a notebook.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class ScoredJob:
    """A LinkedIn job that has been scored against the user's resume."""
    job: dict[str, Any]
    job_requirements: dict[str, Any]
    match_analysis: dict[str, Any]
    match_score: float
    is_fallback: bool = False

    @property
    def title(self) -> str:    return self.job.get("title", "") or "Unknown"
    @property
    def company(self) -> str:  return self.job.get("company", "") or "Unknown"
    @property
    def location(self) -> str: return self.job.get("location", "") or ""
    @property
    def url(self) -> str:      return self.job.get("url", "") or ""
    @property
    def description(self) -> str: return self.job.get("description", "") or ""
    @property
    def matched_skills(self) -> list[str]:
        return self.match_analysis.get("matched_required", []) or []
    @property
    def missing_skills(self) -> list[str]:
        return self.match_analysis.get("missing_required", []) or []

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["title"] = self.title
        d["company"] = self.company
        return d


@dataclass
class PipelineResult:
    resume_data: dict[str, Any]
    jobs_raw: list[dict[str, Any]]
    scored: list[ScoredJob]
    above_threshold: list[ScoredJob]
    below_threshold: list[ScoredJob]
    threshold_pct: int
    used_ai: bool

    def summary(self) -> dict[str, Any]:
        return {
            "total_jobs":        len(self.jobs_raw),
            "scored":            len(self.scored),
            "above_threshold":   len(self.above_threshold),
            "below_threshold":   len(self.below_threshold),
            "threshold_pct":     self.threshold_pct,
            "best_score":        max((s.match_score for s in self.scored), default=0),
            "avg_score":         (sum(s.match_score for s in self.scored)
                                  / len(self.scored)) if self.scored else 0,
            "used_ai":           self.used_ai,
        }


# ── Step 1: Parse resume to text ──────────────────────────────────────────
def parse_resume(file_path: str) -> str:
    """PDF / image / SVG → raw text."""
    from .resume_parser import ResumeParser
    return ResumeParser().parse(file_path)


# ── Step 2: Extract structured data from resume text ─────────────────────
def extract_resume_skills(
    text: str,
    *,
    ai_client=None,
) -> dict[str, Any]:
    """
    Extract skills + experience + education from raw resume text.
    Tries AI extractor first when ai_client is provided; falls back to
    keyword-based extractor on quota / network / parse error.
    """
    if ai_client is not None:
        try:
            from .skills_extractor import SkillsExtractor
            return SkillsExtractor(client=ai_client).extract_from_resume(text)
        except Exception:
            pass  # fall through to keyword extractor
    from .fallback_extractor import extract_resume
    return extract_resume(text)


# ── Step 3: Fetch jobs from LinkedIn ─────────────────────────────────────
def fetch_jobs(
    *,
    job_title: str,
    location: str = "United States",
    num_jobs: int = 30,
    days: int = 30,
    fallback_keywords: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """
    Search LinkedIn. When job_title is set, it is the primary query (in
    quotes for phrase match). Skill keywords are used only as a fallback
    when no title is provided.
    """
    from .linkedin_scraper import LinkedInScraper
    keywords = [job_title] if job_title else (fallback_keywords or [])
    return LinkedInScraper().search_jobs(
        keywords=keywords,
        location=location,
        num_jobs=num_jobs,
        days=days,
        job_title=job_title or None,
    )


# ── Step 4: Score every job's skills against the resume ─────────────────
def match_resume_to_jobs(
    resume_data: dict[str, Any],
    jobs: list[dict[str, Any]],
    *,
    ai_client=None,
) -> list[ScoredJob]:
    """
    For each job:
      1. Extract required skills from the job description
      2. Compute a match score against the resume's skills
    AI extractor is used when ai_client is provided; falls back per-job.
    """
    scored: list[ScoredJob] = []
    use_ai = ai_client is not None

    for job in jobs:
        desc = job.get("description", "")
        if not desc:
            continue

        reqs, analy = None, None
        if use_ai:
            try:
                from .skills_extractor import SkillsExtractor
                ext   = SkillsExtractor(client=ai_client)
                reqs  = ext.extract_from_job(desc, job.get("title", ""))
                analy = ext.calculate_match_score(resume_data, reqs)
            except Exception:
                reqs = analy = None  # fall through

        if reqs is None or analy is None:
            from .fallback_extractor import extract_job, score_match
            reqs  = extract_job(desc, job.get("title", ""))
            analy = score_match(resume_data, reqs)

        scored.append(ScoredJob(
            job=job,
            job_requirements=reqs,
            match_analysis=analy,
            match_score=float(analy.get("score", 0) or 0),
            is_fallback=bool(analy.get("_fallback", False)),
        ))

    # Sort: best match first, then most recent
    from datetime import datetime
    scored.sort(
        key=lambda s: (
            s.match_score,
            s.job.get("posted_date") or datetime.min,
        ),
        reverse=True,
    )
    return scored


# ── Step 5: Filter by user-supplied threshold ────────────────────────────
def filter_by_match(
    scored: list[ScoredJob], min_pct: float,
) -> tuple[list[ScoredJob], list[ScoredJob]]:
    """Return (above_or_equal_threshold, below_threshold)."""
    above = [s for s in scored if s.match_score >= min_pct]
    below = [s for s in scored if s.match_score <  min_pct]
    return above, below


# ── Step 6: Upgrade CV with skills from a specific job ──────────────────
def upgrade_cv(
    resume_data: dict[str, Any],
    scored_job: ScoredJob,
    *,
    ai_client=None,
) -> dict[str, Any]:
    """
    Rewrite the resume to mirror the job's keywords. Requires AI.
    Raises RuntimeError if no ai_client provided.
    """
    if ai_client is None:
        raise RuntimeError("CV upgrade needs an AI client (Gemini/Claude). "
                           "Add an API key in the sidebar.")
    from .ats_optimizer import ATSOptimizer
    return ATSOptimizer(client=ai_client).optimize_resume(
        resume_data, scored_job.job_requirements, scored_job.match_analysis,
    )


# ── End-to-end convenience wrapper ───────────────────────────────────────
def run_full_pipeline(
    *,
    resume_text: str,
    job_title: str,
    location: str = "United States",
    num_jobs: int = 30,
    days: int = 30,
    min_match_pct: float = 25,
    ai_client=None,
) -> PipelineResult:
    """One call that runs every step. Used by tests and the CLI."""
    resume_data = extract_resume_skills(resume_text, ai_client=ai_client)

    fallback_kw = (resume_data.get("technical_skills", []) +
                    resume_data.get("frameworks", []) +
                    resume_data.get("tools", []))[:8]
    jobs = fetch_jobs(
        job_title=job_title, location=location,
        num_jobs=num_jobs, days=days,
        fallback_keywords=fallback_kw,
    )

    scored = match_resume_to_jobs(resume_data, jobs, ai_client=ai_client)
    above, below = filter_by_match(scored, min_match_pct)

    return PipelineResult(
        resume_data=resume_data,
        jobs_raw=jobs,
        scored=scored,
        above_threshold=above,
        below_threshold=below,
        threshold_pct=int(min_match_pct),
        used_ai=ai_client is not None,
    )
