import json
import logging
from typing import Any

from .ai_client import AIClient

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are an expert ATS resume optimizer and career coach. "
    "Rewrite resumes to maximise ATS pass-through rates while keeping content "
    "truthful and compelling for human reviewers. "
    "Always respond with valid JSON only — no markdown fences, no extra text."
)


class ATSOptimizer:
    def __init__(self, client: AIClient):
        self.client = client

    # ── Single job optimisation ───────────────────────────────────────────────
    def optimize_resume(
        self,
        resume_data: dict[str, Any],
        job_data: dict[str, Any],
        match_analysis: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = f"""Optimise this resume for the job posting below. Rules:
1. ONLY use skills/experience already in the resume — never fabricate.
2. Rewrite bullet points to mirror exact keywords from the job description.
3. Quantify achievements where possible.
4. Add missing ATS keywords only where they truthfully apply.
5. Keep summary 3-4 sentences, keyword-rich.
6. Use strong action verbs aligned with job responsibilities.

MISSING REQUIRED SKILLS (add only if genuine): {match_analysis.get('missing_required', [])}
MISSING PREFERRED SKILLS: {match_analysis.get('missing_preferred', [])}
KEY ATS KEYWORDS TO INCLUDE: {job_data.get('ats_keywords', [])}

CURRENT RESUME:
{json.dumps(resume_data, indent=2)}

JOB REQUIREMENTS:
{json.dumps(job_data, indent=2)}

Return JSON with this exact structure:
{{
  "name": "...", "email": "...", "phone": "...", "location": "...",
  "summary": "optimised 3-4 sentence summary with keywords",
  "technical_skills": [], "soft_skills": [], "tools": [],
  "languages": [], "frameworks": [], "certifications": [],
  "education": [],
  "experience": [
    {{
      "title": "...", "company": "...", "duration": "...",
      "achievements": ["rewritten bullet with keywords"]
    }}
  ],
  "projects": [],
  "optimization_notes": ["change 1", "change 2"],
  "added_keywords": ["kw1", "kw2"]
}}"""

        text = self.client.generate(_SYSTEM, prompt, max_tokens=6000)
        return _parse_json(text)

    # ── Bulk optimisation for top N jobs ──────────────────────────────────────
    def bulk_optimize(
        self,
        resume_data: dict[str, Any],
        jobs_with_analysis: list[dict[str, Any]],
        top_n: int = 3,
    ) -> list[dict[str, Any]]:
        sorted_jobs = sorted(
            jobs_with_analysis,
            key=lambda x: x.get("match_score", 0),
            reverse=True,
        )[:top_n]

        results = []
        for item in sorted_jobs:
            job = item["job"]
            logger.info(
                f"Optimising for: {job.get('title')} @ {job.get('company')} "
                f"(score: {item.get('match_score')})"
            )
            optimised = self.optimize_resume(
                resume_data,
                item.get("job_requirements", {}),
                item.get("match_analysis", {}),
            )
            results.append({
                "job": job,
                "match_score": item.get("match_score"),
                "optimized_resume": optimised,
            })

        return results


# ── Helpers ───────────────────────────────────────────────────────────────────
def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end = -1 if lines[-1].strip() in ("```", "```json") else len(lines)
        text = "\n".join(lines[1:end])
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e} — preview: {text[:300]}")
        return {}
