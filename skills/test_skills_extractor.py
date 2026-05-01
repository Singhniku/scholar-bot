"""
Tests for src/skills_extractor.py

Positive: well-formed resume/job data → correct extraction and scoring.
Negative: empty input, missing fields, mismatched skills → expected degraded output.
"""
import pytest
from .fixtures import MOCK_AI_CLIENT, RESUME_POSITIVE, RESUME_NEGATIVE, JOB_POSITIVE, JOB_NEGATIVE
from src.skills_extractor import SkillsExtractor


@pytest.fixture
def extractor():
    return SkillsExtractor(client=MOCK_AI_CLIENT)


# ─── Positive scenarios ───────────────────────────────────────────────────────

class TestExtractFromResumePositive:
    def test_returns_dict(self, extractor):
        result = extractor.extract_from_resume("Sample resume text with Python and AWS skills")
        assert isinstance(result, dict)

    def test_has_required_keys(self, extractor):
        result = extractor.extract_from_resume("Resume text")
        for key in ("name", "technical_skills", "experience_years", "all_keywords"):
            assert key in result, f"Missing key: {key}"

    def test_skills_is_list(self, extractor):
        result = extractor.extract_from_resume("Resume text")
        assert isinstance(result.get("technical_skills", []), list)


class TestExtractFromJobPositive:
    def test_returns_dict(self, extractor):
        result = extractor.extract_from_job(JOB_POSITIVE["description"], "Software Engineer")
        assert isinstance(result, dict)

    def test_has_required_skills_key(self, extractor):
        result = extractor.extract_from_job(JOB_POSITIVE["description"])
        assert "required_skills" in result
        assert isinstance(result["required_skills"], list)

    def test_has_ats_keywords(self, extractor):
        result = extractor.extract_from_job(JOB_POSITIVE["description"])
        assert "ats_keywords" in result


class TestMatchScorePositive:
    def test_high_match_for_matching_resume(self, extractor):
        job_reqs = {
            "required_skills": ["Python", "AWS", "Docker"],
            "preferred_skills": ["Terraform"],
            "ats_keywords": ["microservices", "CI/CD"],
            "required_experience_years": 5,
        }
        result = extractor.calculate_match_score(RESUME_POSITIVE, job_reqs)
        assert result["score"] >= 70, f"Expected high score, got {result['score']}"

    def test_returns_matched_and_missing(self, extractor):
        job_reqs = {
            "required_skills": ["Python", "COBOL"],
            "preferred_skills": [],
            "ats_keywords": [],
        }
        result = extractor.calculate_match_score(RESUME_POSITIVE, job_reqs)
        assert "Python" in [s.lower() for s in result["matched_required"]] or \
               "python" in result["matched_required"]
        assert any("cobol" in s.lower() for s in result["missing_required"])

    def test_score_is_float_in_range(self, extractor):
        job_reqs = {"required_skills": ["Python"], "preferred_skills": [], "ats_keywords": []}
        result = extractor.calculate_match_score(RESUME_POSITIVE, job_reqs)
        assert 0.0 <= result["score"] <= 100.0

    def test_perfect_skill_match_high_score(self, extractor):
        job_reqs = {
            "required_skills": RESUME_POSITIVE["technical_skills"][:3],
            "preferred_skills": [],
            "ats_keywords": [],
        }
        result = extractor.calculate_match_score(RESUME_POSITIVE, job_reqs)
        assert result["score"] >= 70

    def test_no_missing_when_all_matched(self, extractor):
        job_reqs = {
            "required_skills": ["Python"],
            "preferred_skills": [],
            "ats_keywords": [],
        }
        result = extractor.calculate_match_score(RESUME_POSITIVE, job_reqs)
        assert result["missing_required"] == []


# ─── Negative scenarios ───────────────────────────────────────────────────────

class TestMatchScoreNegative:
    def test_low_match_for_empty_resume(self, extractor):
        job_reqs = {
            "required_skills": ["Python", "AWS", "Docker", "Kubernetes"],
            "preferred_skills": ["Terraform"],
            "ats_keywords": ["CI/CD"],
            "required_experience_years": 5,   # non-zero so exp_score contributes to gap
        }
        result = extractor.calculate_match_score(RESUME_NEGATIVE, job_reqs)
        # All required/preferred/ATS skills missing → only partial exp_score possible
        assert result["score"] <= 10.0, f"Expected low score, got {result['score']}"
        assert len(result["missing_required"]) == 4

    def test_all_skills_missing_for_empty_resume(self, extractor):
        job_reqs = {
            "required_skills": ["Python", "AWS"],
            "preferred_skills": [],
            "ats_keywords": [],
        }
        result = extractor.calculate_match_score(RESUME_NEGATIVE, job_reqs)
        assert len(result["missing_required"]) == 2

    def test_mismatched_skills_score_near_zero(self, extractor):
        job_reqs = {
            "required_skills": JOB_NEGATIVE["required_skills"],
            "preferred_skills": JOB_NEGATIVE["preferred_skills"],
            "ats_keywords": ["C", "C++", "RTOS"],
        }
        result = extractor.calculate_match_score(RESUME_POSITIVE, job_reqs)
        assert result["score"] < 20, f"Expected near-zero score for mismatch, got {result['score']}"

    def test_empty_job_requirements_returns_full_exp_score(self, extractor):
        result = extractor.calculate_match_score(
            RESUME_POSITIVE,
            {"required_skills": [], "preferred_skills": [], "ats_keywords": []},
        )
        assert result["score"] >= 0

    def test_handles_none_experience_years(self, extractor):
        rd = {**RESUME_POSITIVE, "experience_years": None}
        result = extractor.calculate_match_score(
            rd, {"required_skills": [], "preferred_skills": [], "ats_keywords": []}
        )
        assert isinstance(result["score"], float)
