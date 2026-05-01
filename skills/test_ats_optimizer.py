"""
Tests for src/ats_optimizer.py

Positive: valid resume + matching job → well-structured optimised resume.
Negative: empty data, no job requirements → graceful degraded output.
"""
import pytest
from .fixtures import MOCK_AI_CLIENT, RESUME_POSITIVE, RESUME_NEGATIVE, JOB_POSITIVE, JOB_NEGATIVE
from src.ats_optimizer import ATSOptimizer


@pytest.fixture
def optimizer():
    return ATSOptimizer(client=MOCK_AI_CLIENT)


@pytest.fixture
def good_job_reqs():
    return {
        "required_skills": ["Python", "AWS", "Docker"],
        "preferred_skills": ["Terraform"],
        "ats_keywords": ["microservices", "CI/CD", "Kubernetes"],
    }

@pytest.fixture
def good_match_analysis():
    return {
        "score": 85.0,
        "matched_required": ["Python", "AWS", "Docker"],
        "missing_required": [],
        "matched_preferred": ["Terraform"],
        "missing_preferred": [],
        "matched_ats_keywords": ["Kubernetes"],
    }


# ─── Positive scenarios ───────────────────────────────────────────────────────

class TestOptimizeResumePositive:
    def test_returns_dict(self, optimizer, good_job_reqs, good_match_analysis):
        result = optimizer.optimize_resume(RESUME_POSITIVE, good_job_reqs, good_match_analysis)
        assert isinstance(result, dict)

    def test_has_summary(self, optimizer, good_job_reqs, good_match_analysis):
        result = optimizer.optimize_resume(RESUME_POSITIVE, good_job_reqs, good_match_analysis)
        assert "summary" in result
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 20

    def test_has_optimization_notes(self, optimizer, good_job_reqs, good_match_analysis):
        result = optimizer.optimize_resume(RESUME_POSITIVE, good_job_reqs, good_match_analysis)
        assert "optimization_notes" in result
        assert isinstance(result["optimization_notes"], list)

    def test_preserves_name(self, optimizer, good_job_reqs, good_match_analysis):
        result = optimizer.optimize_resume(RESUME_POSITIVE, good_job_reqs, good_match_analysis)
        assert result.get("name") == RESUME_POSITIVE["name"]

    def test_technical_skills_is_list(self, optimizer, good_job_reqs, good_match_analysis):
        result = optimizer.optimize_resume(RESUME_POSITIVE, good_job_reqs, good_match_analysis)
        assert isinstance(result.get("technical_skills", []), list)


class TestBulkOptimizePositive:
    def test_returns_correct_count(self, optimizer):
        jobs = [
            {
                "job": JOB_POSITIVE,
                "job_requirements": {"required_skills": ["Python"], "preferred_skills": [], "ats_keywords": []},
                "match_analysis": {"missing_required": [], "missing_preferred": []},
                "match_score": 85.0,
            },
            {
                "job": JOB_NEGATIVE,
                "job_requirements": {"required_skills": ["C++"], "preferred_skills": [], "ats_keywords": []},
                "match_analysis": {"missing_required": ["C++"], "missing_preferred": []},
                "match_score": 10.0,
            },
        ]
        results = optimizer.bulk_optimize(RESUME_POSITIVE, jobs, top_n=2)
        assert len(results) == 2

    def test_sorted_by_score_descending(self, optimizer):
        jobs = [
            {"job": JOB_NEGATIVE, "job_requirements": {}, "match_analysis": {}, "match_score": 10.0},
            {"job": JOB_POSITIVE, "job_requirements": {}, "match_analysis": {}, "match_score": 85.0},
        ]
        results = optimizer.bulk_optimize(RESUME_POSITIVE, jobs, top_n=2)
        scores = [r["match_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_top_n_limits_output(self, optimizer):
        jobs = [
            {"job": JOB_POSITIVE, "job_requirements": {}, "match_analysis": {}, "match_score": 80.0},
            {"job": JOB_NEGATIVE, "job_requirements": {}, "match_analysis": {}, "match_score": 20.0},
        ]
        results = optimizer.bulk_optimize(RESUME_POSITIVE, jobs, top_n=1)
        assert len(results) == 1


# ─── Negative scenarios ───────────────────────────────────────────────────────

class TestOptimizeResumeNegative:
    def test_empty_resume_does_not_crash(self, optimizer):
        result = optimizer.optimize_resume(RESUME_NEGATIVE, {}, {})
        assert isinstance(result, dict)

    def test_empty_job_reqs_does_not_crash(self, optimizer):
        result = optimizer.optimize_resume(RESUME_POSITIVE, {}, {})
        assert isinstance(result, dict)

    def test_bulk_optimize_empty_jobs_returns_empty(self, optimizer):
        results = optimizer.bulk_optimize(RESUME_POSITIVE, [], top_n=3)
        assert results == []

    def test_bulk_optimize_zero_top_n(self, optimizer):
        jobs = [{"job": JOB_POSITIVE, "job_requirements": {}, "match_analysis": {}, "match_score": 80.0}]
        results = optimizer.bulk_optimize(RESUME_POSITIVE, jobs, top_n=0)
        assert results == []
