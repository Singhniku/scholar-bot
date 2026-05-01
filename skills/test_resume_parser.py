"""
Tests for src/resume_parser.py

Positive: valid file paths and formats → non-empty text.
Negative: missing file, unsupported extension, empty PDF → proper errors / empty string.
"""
import os
import tempfile
import pytest
from src.resume_parser import ResumeParser


@pytest.fixture
def parser():
    return ResumeParser()


# ─── Positive scenarios ───────────────────────────────────────────────────────

class TestResumeParserfPositive:
    def test_supported_extensions_set(self, parser):
        assert ".pdf" in parser.SUPPORTED
        assert ".jpg" in parser.SUPPORTED
        assert ".jpeg" in parser.SUPPORTED
        assert ".png" in parser.SUPPORTED
        assert ".svg" in parser.SUPPORTED

    def test_parse_text_pdf(self, parser):
        """Create a minimal real PDF with reportlab and parse it."""
        pytest.importorskip("reportlab")
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph
        from reportlab.lib.styles import getSampleStyleSheet

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            doc = SimpleDocTemplate(tmp.name, pagesize=letter)
            styles = getSampleStyleSheet()
            doc.build([Paragraph("Python Developer with AWS and Docker skills", styles["Normal"])])
            tmp_path = tmp.name

        try:
            text = parser.parse(tmp_path)
            assert "Python" in text or len(text) > 5
        finally:
            os.unlink(tmp_path)


# ─── Negative scenarios ───────────────────────────────────────────────────────

class TestResumeParserNegative:
    def test_missing_file_raises_file_not_found(self, parser):
        with pytest.raises(FileNotFoundError):
            parser.parse("/tmp/does_not_exist_12345.pdf")

    def test_unsupported_extension_raises_value_error(self, parser):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            tmp_path = tmp.name
        try:
            with pytest.raises(ValueError, match="Unsupported format"):
                parser.parse(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_unsupported_txt_raises(self, parser):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w") as tmp:
            tmp.write("Python Developer")
            tmp_path = tmp.name
        try:
            with pytest.raises(ValueError):
                parser.parse(tmp_path)
        finally:
            os.unlink(tmp_path)
