import json
import logging
from typing import Any

from .ai_client import AIClient

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are an expert technical recruiter and resume analyst. "
    "Extract structured information from resumes and job descriptions with high accuracy. "
    "Always respond with valid JSON only — no markdown fences, no extra text."
)


class SkillsExtractor:
    def __init__(self, client: AIClient):
        self.client = client

    # ── Resume extraction ─────────────────────────────────────────────────────
    def extract_from_resume(self, resume_text: str) -> dict[str, Any]:
        prompt = f"""Extract all information from this resume and return JSON with this exact structure:
{{
  "name": "Full Name",
  "email": "email@example.com",
  "phone": "phone number",
  "location": "city, state/country",
  "summary": "professional summary or objective",
  "experience_years": 5,
  "current_title": "current or most recent job title",
  "technical_skills": ["Python", "SQL"],
  "soft_skills": ["Leadership", "Communication"],
  "tools": ["Git", "Docker", "AWS"],
  "languages": ["Python", "JavaScript"],
  "frameworks": ["React", "Django"],
  "certifications": ["AWS Certified"],
  "education": [
    {{"degree": "BS Computer Science", "institution": "MIT", "year": 2020}}
  ],
  "experience": [
    {{
      "title": "Software Engineer",
      "company": "Acme Corp",
      "duration": "Jan 2021 - Present",
      "achievements": ["Led team of 5", "Reduced latency by 30%"]
    }}
  ],
  "projects": [
    {{"name": "Project Name", "description": "what it does", "technologies": ["Python"]}}
  ],
  "all_keywords": ["keyword1", "keyword2"]
}}

Resume text:
{resume_text}"""

        text = self.client.generate(_SYSTEM, prompt, max_tokens=4096)
        return _parse_json(text)

    # ── Job description extraction ────────────────────────────────────────────
    def extract_from_job(self, job_description: str, job_title: str = "") -> dict[str, Any]:
        prompt = f"""Extract all requirements from this job description and return JSON:
{{
  "title": "Job Title",
  "required_skills": ["Python", "AWS"],
  "preferred_skills": ["Kubernetes"],
  "required_experience_years": 3,
  "education_required": "Bachelor's degree",
  "key_responsibilities": ["Build APIs", "Lead team"],
  "ats_keywords": ["keyword1", "keyword2"],
  "seniority_level": "Mid-level",
  "job_type": "Full-time"
}}

Job Title: {job_title}
Job Description:
{job_description}"""

        text = self.client.generate(_SYSTEM, prompt, max_tokens=2048)
        return _parse_json(text)

    # ── Match scoring (pure Python — no AI call needed) ───────────────────────
    def calculate_match_score(
        self,
        resume_data: dict[str, Any],
        job_requirements: dict[str, Any],
    ) -> dict[str, Any]:
        resume_all = {
            s.lower()
            for s in (
                resume_data.get("all_keywords", [])
                + resume_data.get("technical_skills", [])
                + resume_data.get("tools", [])
                + resume_data.get("frameworks", [])
                + resume_data.get("languages", [])
            )
        }

        required  = [s.lower() for s in job_requirements.get("required_skills", [])]
        preferred = [s.lower() for s in job_requirements.get("preferred_skills", [])]
        ats_kws   = [s.lower() for s in job_requirements.get("ats_keywords", [])]

        matched_req  = [s for s in required  if s in resume_all]
        missing_req  = [s for s in required  if s not in resume_all]
        matched_pref = [s for s in preferred if s in resume_all]
        missing_pref = [s for s in preferred if s not in resume_all]
        matched_ats  = [s for s in ats_kws   if s in resume_all]

        req_score  = (len(matched_req)  / max(len(required),  1)) * 70
        pref_score = (len(matched_pref) / max(len(preferred), 1)) * 20
        ats_score  = (len(matched_ats)  / max(len(ats_kws),   1)) * 10

        exp_req = job_requirements.get("required_experience_years") or 0
        exp_can = resume_data.get("experience_years") or 0
        exp_score = min(exp_can / exp_req, 1.0) * 10 if exp_req > 0 else 10

        total = min(req_score + pref_score + ats_score + exp_score, 100)

        return {
            "score": round(total, 1),
            "matched_required":  matched_req,
            "missing_required":  missing_req,
            "matched_preferred": matched_pref,
            "missing_preferred": missing_pref,
            "matched_ats_keywords": matched_ats,
            "experience_gap": max(int(exp_req) - int(exp_can), 0),
        }


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
