"""
Tests for src/resume_generator.py

Positive: valid resume data → PDF and Markdown files created with correct content.
Negative: missing fields, empty resume → graceful output (no crash).
"""
import os
import tempfile
from pathlib import Path
import pytest
from .fixtures import RESUME_POSITIVE, RESUME_NEGATIVE
from src.resume_generator import ResumeGenerator


@pytest.fixture
def generator():
    return ResumeGenerator()


# ─── Positive scenarios ───────────────────────────────────────────────────────

class TestGeneratePDFPositive:
    def test_pdf_file_created(self, generator):
        pytest.importorskip("reportlab")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            path = tmp.name
        try:
            result = generator.generate_pdf(RESUME_POSITIVE, path)
            assert Path(result).exists()
            assert Path(result).stat().st_size > 1000  # real PDF, not empty
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_pdf_returns_path(self, generator):
        pytest.importorskip("reportlab")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            path = tmp.name
        try:
            result = generator.generate_pdf(RESUME_POSITIVE, path)
            assert result == path
        finally:
            if os.path.exists(path):
                os.unlink(path)


class TestGenerateMarkdownPositive:
    def test_markdown_file_created(self, generator):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".md", mode="w") as tmp:
            path = tmp.name
        try:
            result = generator.generate_markdown(RESUME_POSITIVE, path)
            assert Path(result).exists()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_markdown_contains_name(self, generator):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".md", mode="w") as tmp:
            path = tmp.name
        try:
            generator.generate_markdown(RESUME_POSITIVE, path)
            content = Path(path).read_text()
            assert RESUME_POSITIVE["name"] in content
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_markdown_contains_skills(self, generator):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".md", mode="w") as tmp:
            path = tmp.name
        try:
            generator.generate_markdown(RESUME_POSITIVE, path)
            content = Path(path).read_text()
            assert "Python" in content
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_markdown_contains_experience(self, generator):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".md", mode="w") as tmp:
            path = tmp.name
        try:
            generator.generate_markdown(RESUME_POSITIVE, path)
            content = Path(path).read_text()
            assert "TechCorp" in content
        finally:
            if os.path.exists(path):
                os.unlink(path)


class TestGenerateJobReportPositive:
    def test_report_created(self, generator):
        from .fixtures import JOB_POSITIVE
        ranked = [{
            "job": JOB_POSITIVE,
            "match_score": 85.0,
            "match_analysis": {"matched_required": ["Python"], "missing_required": []},
        }]
        with tempfile.NamedTemporaryFile(delete=False, suffix=".md", mode="w") as tmp:
            path = tmp.name
        try:
            result = generator.generate_job_report(ranked, path)
            assert Path(result).exists()
            content = Path(result).read_text()
            assert "Acme Cloud" in content
        finally:
            if os.path.exists(path):
                os.unlink(path)


# ─── Negative scenarios ───────────────────────────────────────────────────────

class TestGenerateNegative:
    def test_empty_resume_pdf_does_not_crash(self, generator):
        pytest.importorskip("reportlab")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            path = tmp.name
        try:
            result = generator.generate_pdf(RESUME_NEGATIVE, path)
            assert Path(result).exists()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_empty_resume_markdown_does_not_crash(self, generator):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".md", mode="w") as tmp:
            path = tmp.name
        try:
            generator.generate_markdown(RESUME_NEGATIVE, path)
            assert Path(path).exists()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_empty_job_list_report_does_not_crash(self, generator):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".md", mode="w") as tmp:
            path = tmp.name
        try:
            generator.generate_job_report([], path)
            assert Path(path).exists()
        finally:
            if os.path.exists(path):
                os.unlink(path)
