"""
Tests for src/ai_client.py

Positive scenarios: valid config, correct responses.
Negative scenarios: missing key, bad provider, quota errors handled gracefully.
"""
import pytest
from .fixtures import MOCK_AI_CLIENT


# ─── Positive scenarios ───────────────────────────────────────────────────────

class TestMockAIClientPositive:
    def test_generates_text(self):
        result = MOCK_AI_CLIENT.generate("sys", "user message")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_provider_label(self):
        assert MOCK_AI_CLIENT.provider_label == "Mock AI (no API calls)"

    def test_from_keys_returns_instance(self):
        c = MOCK_AI_CLIENT.from_keys(provider="mock", google_key="", anthropic_key="")
        assert c is not None

    def test_routes_resume_prompt(self):
        result = MOCK_AI_CLIENT.generate("sys", "Extract information from this resume text")
        assert "name" in result.lower() or "Alex" in result

    def test_routes_job_prompt(self):
        result = MOCK_AI_CLIENT.generate("sys", "Extract all requirements from this job description")
        assert "required_skills" in result

    def test_routes_optimise_prompt(self):
        result = MOCK_AI_CLIENT.generate("sys", "Optimise this resume for the job posting")
        assert "optimization_notes" in result


# ─── Negative scenarios ───────────────────────────────────────────────────────

class TestAIClientNegative:
    def test_unknown_provider_raises(self):
        from src.ai_client import AIClient
        with pytest.raises(ValueError, match="Unknown AI provider"):
            AIClient(provider="openai", api_key="dummy")

    def test_gemini_missing_key_raises(self):
        from src.ai_client import AIClient
        import os, unittest.mock as mock
        with mock.patch.dict(os.environ, {"AI_PROVIDER": "gemini", "GOOGLE_API_KEY": ""}):
            with pytest.raises(RuntimeError, match="No API key"):
                AIClient.from_env()

    def test_anthropic_missing_key_raises(self):
        from src.ai_client import AIClient
        import os, unittest.mock as mock
        with mock.patch.dict(os.environ, {"AI_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": ""}):
            with pytest.raises(RuntimeError, match="No API key"):
                AIClient.from_env()
