"""
app/ai/parsers/image_parser.py
==============================
Image (JPG / PNG / TIFF / BMP / WEBP) → DocumentRepresentation

Pipeline:
1. Pillow: load + preprocess (grayscale, contrast enhancement, optional deskew).
2. pytesseract: OCR with multi-language support (eng + ara by default).
3. Word bounding boxes from pytesseract's DICT output → group words into lines
   via Y-coordinate clustering → produce DocumentBlock per line.

Coordinates: always available (pixel-space, page=0 for single-page images).
Language: auto-detected via Arabic unicode character ratio.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.ai.interfaces.base_parser import BaseParser
from app.core.config import get_settings
from app.schemas.document_representation import (
    BoundingBox,
    DocumentBlock,
    DocumentRepresentation,
    DocumentTable,
)

try:
    from PIL import Image, ImageEnhance, ImageFilter  # type: ignore
    _PILLOW_AVAILABLE = True
except ImportError:
    _PILLOW_AVAILABLE = False

try:
    import pytesseract  # type: ignore
    from pytesseract import Output  # type: ignore
    _TESSERACT_AVAILABLE = True
except ImportError:
    _TESSERACT_AVAILABLE = False

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False

_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")


def _detect_language(text: str) -> tuple[str, bool]:
    if not text:
        return "unknown", False
    arabic_chars = len(_ARABIC_RE.findall(text))
    latin_chars = sum(1 for c in text if c.isascii() and c.isalpha())
    total = arabic_chars + latin_chars
    if total == 0:
        return "unknown", False
    ratio = arabic_chars / total
    if ratio > 0.70:
        return "ar", True
    if ratio > 0.20:
        return "mixed", True
    return "en", False


def _clean(text: str | None) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _cv2_deskew(gray: Any) -> Any:
    """
    Estimate and correct skew using cv2.minAreaRect on the largest contour.
    Falls back gracefully if angle cannot be determined.
    """
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore

        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        coords = np.column_stack(np.where(thresh > 0))
        if len(coords) < 10:
            return gray
        angle = cv2.minAreaRect(coords)[-1]
        # minAreaRect returns angles in [-90, 0); normalize to [-45, 45]
        if angle < -45:
            angle = 90 + angle
        if abs(angle) < 0.5:
            return gray
        h, w = gray.shape[:2]
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        rotated = cv2.warpAffine(
            gray, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return rotated
    except Exception:
        return gray


def _pillow_deskew(image: Any) -> Any:
    """
    Coarse Pillow-based deskew estimation using horizontal projection profile.
    Tries a small range of rotation angles and picks the one with highest
    row-variance (most well-separated text lines).
    """
    try:
        import math
        from PIL import Image  # type: ignore

        best_angle = 0.0
        best_score = -1.0

        for angle in [a * 0.5 for a in range(-6, 7)]:  # -3° to +3° in 0.5° steps
            rotated = image.rotate(angle, expand=False, fillcolor=255)
            import struct

            # Projection profile: sum each row's pixel values (lower = darker text row)
            w, h = rotated.size
            pixels = list(rotated.getdata())
            row_sums = [
                sum(pixels[r * w:(r + 1) * w]) / w
                for r in range(h)
            ]
            mean = sum(row_sums) / len(row_sums)
            variance = sum((v - mean) ** 2 for v in row_sums) / len(row_sums)
            if variance > best_score:
                best_score = variance
                best_angle = angle

        if abs(best_angle) < 0.3:
            return image
        return image.rotate(best_angle, expand=False, fillcolor=255)
    except Exception:
        return image


class ImageParser(BaseParser):
    """
    Parse an image file (JPG / PNG / TIFF / BMP / WEBP) via OCR.
    Requires Pillow and pytesseract (+ Tesseract binary with Arabic language pack).
    """

    async def parse(self, file_bytes: bytes, filename: str) -> dict:
        rep = self._parse_to_representation(file_bytes, filename)
        return {"representation": rep}

    def _parse_to_representation(
        self, file_bytes: bytes, filename: str
    ) -> DocumentRepresentation:
        if not _PILLOW_AVAILABLE:
            raise RuntimeError("Pillow is not installed. Run: pip install Pillow")
        if not _TESSERACT_AVAILABLE:
            raise RuntimeError(
                "pytesseract is not installed. Run: pip install pytesseract. "
                "Also install Tesseract binary: https://tesseract-ocr.github.io/tessdoc/Installation.html"
            )

        settings = get_settings()
        lang = getattr(settings, "TESSERACT_LANG", "eng+ara")

        import io
        from PIL import Image, ImageEnhance  # type: ignore
        import pytesseract  # type: ignore
        from pytesseract import Output  # noqa: F401

        # ── Image preprocessing ───────────────────────────────────────────────
        image = Image.open(io.BytesIO(file_bytes))
        image = self._preprocess(image)

        # ── OCR: word-level bounding boxes ────────────────────────────────────
        try:
            ocr_data: dict[str, list[Any]] = pytesseract.image_to_data(
                image,
                lang=lang,
                output_type=pytesseract.Output.DICT,
                config="--oem 1 --psm 3",
            )
        except pytesseract.TesseractNotFoundError:
            raise RuntimeError(
                "Tesseract binary not found. Install Tesseract and ensure it is on PATH. "
                "Arabic support requires the 'ara' language pack."
            )

        # ── Group words into lines ────────────────────────────────────────────
        lines = self._group_words_to_lines(ocr_data, image)

        # ── Build DocumentBlocks from lines ──────────────────────────────────
        all_rows: list[str] = []
        blocks: list[DocumentBlock] = []
        for i, (line_text, bbox) in enumerate(lines):
            clean = _clean(line_text)
            if not clean:
                continue
            all_rows.append(clean)
            blocks.append(DocumentBlock(
                block_id=f"b{i}",
                block_type="text",
                raw_text=clean,
                page=0,
                bbox=bbox,
            ))

        full_text = "\n".join(all_rows)
        detected_lang, has_rtl = _detect_language(full_text)

        warnings: list[str] = []
        if not full_text.strip():
            warnings.append("OCR produced no text. Image may be blank, low-quality, or unsupported.")

        return DocumentRepresentation(
            source_format="image",
            filename=filename,
            full_text=full_text,
            pages=[full_text],
            blocks=blocks,
            tables=[],
            all_rows=all_rows,
            coordinates_available=True,
            language_hint=detected_lang,
            has_rtl=has_rtl,
            parse_warnings=warnings,
            page_count=1,
        )

    # ── Image preprocessing ───────────────────────────────────────────────────

    @staticmethod
    def _preprocess(image: Any) -> Any:
        """
        Multi-step preprocessing to improve OCR accuracy.

        Path A (cv2 available):
          1. Convert to grayscale numpy array
          2. CLAHE contrast enhancement (clip limit 3.0, tile 8×8)
          3. Gaussian denoising (3×3 kernel)
          4. Deskew via minAreaRect on thresholded contours
          5. Return as PIL.Image for pytesseract

        Path B (Pillow only fallback):
          1. Greyscale conversion
          2. Contrast boost (1.6×) via ImageEnhance
          3. Mild unsharp-mask sharpening
          4. Coarse deskew estimation via horizontal projection profile
        """
        from PIL import Image, ImageEnhance, ImageFilter  # type: ignore

        # Normalise mode
        if image.mode not in ("L", "RGB"):
            image = image.convert("RGB")

        if _CV2_AVAILABLE:
            # ── OpenCV path ──────────────────────────────────────────────────
            import numpy as np  # type: ignore
            import cv2  # type: ignore

            img_rgb = image.convert("RGB")
            arr = np.array(img_rgb)
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

            # CLAHE contrast enhancement
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            gray = clahe.apply(gray)

            # Gaussian denoising
            gray = cv2.GaussianBlur(gray, (3, 3), 0)

            # Deskew
            gray = _cv2_deskew(gray)

            return Image.fromarray(gray)

        else:
            # ── Pillow-only path ─────────────────────────────────────────────
            gray = image.convert("L")

            # Contrast boost
            gray = ImageEnhance.Contrast(gray).enhance(1.6)

            # Sharpening via unsharp mask
            gray = gray.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))

            # Coarse deskew (Pillow)
            gray = _pillow_deskew(gray)

            return gray

    # ── Word → line grouping ──────────────────────────────────────────────────

    @staticmethod
    def _group_words_to_lines(
        ocr_data: dict[str, list[Any]],
        image: Any,
    ) -> list[tuple[str, BoundingBox]]:
        """
        Group OCR word-level data into text lines using Y-coordinate proximity.
        Returns list of (line_text, BoundingBox).
        """
        n = len(ocr_data["text"])
        words: list[dict[str, Any]] = []

        for i in range(n):
            conf = float(ocr_data["conf"][i])
            text = (ocr_data["text"][i] or "").strip()
            if conf < 10 or not text:  # skip very low-confidence / empty
                continue
            words.append({
                "text": text,
                "left": ocr_data["left"][i],
                "top": ocr_data["top"][i],
                "width": ocr_data["width"][i],
                "height": ocr_data["height"][i],
                "conf": conf,
            })

        if not words:
            return []

        # Sort by reading order: top (Y) first, then left (X)
        words.sort(key=lambda w: (w["top"], w["left"]))

        # Cluster words into lines: words within LINE_HEIGHT_TOLERANCE px of each other
        LINE_HEIGHT_TOLERANCE = 8
        lines: list[list[dict[str, Any]]] = []
        current_line: list[dict[str, Any]] = []
        current_y: float = -999

        for word in words:
            if abs(word["top"] - current_y) > LINE_HEIGHT_TOLERANCE:
                if current_line:
                    lines.append(current_line)
                current_line = [word]
                current_y = word["top"]
            else:
                current_line.append(word)

        if current_line:
            lines.append(current_line)

        # Convert lines to (text, bbox) pairs
        result: list[tuple[str, BoundingBox]] = []
        for line_words in lines:
            line_words.sort(key=lambda w: w["left"])
            line_text = " ".join(w["text"] for w in line_words)
            x0 = min(w["left"] for w in line_words)
            y0 = min(w["top"] for w in line_words)
            x1 = max(w["left"] + w["width"] for w in line_words)
            y1 = max(w["top"] + w["height"] for w in line_words)
            result.append((line_text, BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1, page=0)))

        return result
