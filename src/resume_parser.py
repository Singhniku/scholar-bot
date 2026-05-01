import os
import sys
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ResumeParser:
    """Parses resume files in PDF, JPG, JPEG, PNG, and SVG formats."""

    SUPPORTED = {".pdf", ".jpg", ".jpeg", ".png", ".svg"}

    def parse(self, file_path: str) -> str:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Resume file not found: {file_path}")

        ext = path.suffix.lower()
        if ext not in self.SUPPORTED:
            raise ValueError(
                f"Unsupported format '{ext}'. Supported: {', '.join(self.SUPPORTED)}"
            )

        logger.info(f"Parsing resume: {file_path} (format: {ext})")

        if ext == ".pdf":
            return self._parse_pdf(file_path)
        elif ext == ".svg":
            return self._parse_svg(file_path)
        else:
            return self._parse_image(file_path)

    def _parse_pdf(self, file_path: str) -> str:
        try:
            import pdfplumber
        except ImportError:
            raise ImportError("pdfplumber is required: pip install pdfplumber")

        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text(x_tolerance=3, y_tolerance=3)
                if text:
                    text_parts.append(text)

                # Also extract tables if present
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row:
                            row_text = " | ".join(cell or "" for cell in row)
                            text_parts.append(row_text)

        if not text_parts:
            logger.warning("No text extracted from PDF; attempting OCR fallback")
            return self._pdf_ocr_fallback(file_path)

        return "\n".join(text_parts)

    def _pdf_ocr_fallback(self, file_path: str) -> str:
        """Convert PDF pages to images and OCR them."""
        try:
            from pdf2image import convert_from_path
        except ImportError:
            logger.warning("pdf2image not installed; cannot OCR scanned PDF")
            return ""

        images = convert_from_path(file_path, dpi=300)
        return "\n".join(self._ocr_image(img) for img in images)

    def _parse_svg(self, file_path: str) -> str:
        """Convert SVG to PNG then OCR."""
        try:
            import cairosvg
        except ImportError:
            raise ImportError("cairosvg is required for SVG: pip install cairosvg")

        try:
            from PIL import Image
            import io
        except ImportError:
            raise ImportError("Pillow is required: pip install Pillow")

        png_bytes = cairosvg.svg2png(url=file_path, dpi=300)
        img = Image.open(io.BytesIO(png_bytes))
        return self._ocr_image(img)

    def _parse_image(self, file_path: str) -> str:
        try:
            from PIL import Image
        except ImportError:
            raise ImportError("Pillow is required: pip install Pillow")

        img = Image.open(file_path)
        return self._ocr_image(img)

    def _ocr_image(self, img) -> str:
        try:
            import pytesseract
            from PIL import ImageFilter, ImageEnhance
        except ImportError:
            raise ImportError(
                "pytesseract and Pillow are required for image OCR: "
                "pip install pytesseract Pillow"
            )

        # Preprocess for better OCR accuracy
        img = img.convert("L")  # grayscale
        img = img.filter(ImageFilter.SHARPEN)
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)

        config = "--oem 3 --psm 6 -c preserve_interword_spaces=1"
        text = pytesseract.image_to_string(img, config=config)
        return text.strip()
