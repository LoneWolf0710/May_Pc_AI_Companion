"""EasyOCR Reader — Tier 2 Option B for May's 3-Tier Screen Understanding.

Uses EasyOCR (lightweight OCR model) to extract visible text from screenshots
when the Windows UIAccessibility API fails or returns no useful data (e.g.,
games, custom UI frameworks, remote desktop sessions).

From MAY_FINAL_ARCHITECTURE.md Part 3:
  TIER 2: STRUCTURED ANALYSIS (On change, ~100ms)
    OPTION B (for apps without accessibility):
      EasyOCR (lightweight model) → extract visible text
      → pip install easyocr
      → ~500MB RAM, no VRAM needed for CPU mode

Performance:
  - RAM: ~300-500MB (one-time model load)
  - Speed: ~200-500ms per screenshot on CPU
  - No VRAM required — runs on CPU only
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("may.intelligence.ocr_reader")

# Lazy imports — heavy libs loaded on first use
_easyocr = None
_pil_image = None
_np = None


def _ensure_easyocr():
    """Lazy-load EasyOCR (heavy import, ~300MB RAM)."""
    global _easyocr
    if _easyocr is None:
        try:
            import easyocr
            _easyocr = easyocr
        except ImportError:
            raise ImportError(
                "EasyOCR is required for Tier 2 Option B screen reading. "
                "Install with: pip install easyocr"
            )
    return _easyocr


def _ensure_pil():
    """Lazy-load PIL (Pillow)."""
    global _pil_image
    if _pil_image is None:
        from PIL import Image
        _pil_image = Image
    return _pil_image


def _ensure_numpy():
    """Lazy-load numpy."""
    global _np
    if _np is None:
        import numpy as np
        _np = np
    return _np


@dataclass
class OCRResult:
    """Result from an EasyOCR screen read."""
    text_lines: list[str] = field(default_factory=list)
    full_text: str = ""
    line_count: int = 0
    confidence_avg: float = 0.0
    read_time_ms: float = 0
    image_size: tuple[int, int] = (0, 0)

    def to_dict(self) -> dict:
        return {
            "text_lines": self.text_lines,
            "full_text": self.full_text[:2000],
            "line_count": self.line_count,
            "confidence_avg": round(self.confidence_avg, 3),
            "read_time_ms": round(self.read_time_ms, 1),
            "image_size": list(self.image_size),
        }


class OCRReader:
    """Lightweight screen text extraction using EasyOCR.

    Runs on CPU only — no VRAM required. Uses CRNN-based text detection
    and recognition models optimized for speed.

    Usage:
        reader = OCRReader()
        if reader.is_available():
            result = reader.read_screenshot(screenshot_path)
            print(result.full_text)
    """

    def __init__(self, lang: str = "en", use_gpu: bool = False):
        """
        Args:
            lang: Language for OCR (default: English).
            use_gpu: Whether to use GPU acceleration (not recommended on 6GB VRAM).
        """
        self._lang = lang
        self._use_gpu = use_gpu
        self._ocr_instance = None
        self._available: bool | None = None
        self._last_result: OCRResult | None = None

    def is_available(self) -> bool:
        """Check if EasyOCR is installed and usable."""
        if self._available is not None:
            return self._available
        try:
            _ensure_easyocr()
            self._available = True
        except (ImportError, OSError) as e:
            logger.debug("EasyOCR not available: %s", e)
            self._available = False
        return self._available

    def _get_ocr(self):
        """Get or create the EasyOCR Reader instance (lazy init)."""
        if self._ocr_instance is None:
            easyocr_module = _ensure_easyocr()
            self._ocr_instance = easyocr_module.Reader(
                [self._lang],
                gpu=self._use_gpu,
                verbose=False,  # Suppress EasyOCR console output
            )
            logger.info("EasyOCR initialized (lang=%s, gpu=%s)", self._lang, self._use_gpu)
        return self._ocr_instance

    def read_screenshot(self, image_path: str) -> OCRResult:
        """Extract text from a screenshot file.

        Args:
            image_path: Path to a PNG/JPG screenshot file.

        Returns:
            OCRResult with extracted text lines and metadata.
        """
        if not self.is_available():
            return OCRResult()

        start_time = time.monotonic()

        try:
            import os
            if not os.path.exists(image_path):
                logger.debug("Screenshot not found: %s", image_path)
                return OCRResult()

            # Resize for speed — downscale to max 1280px width
            Image = _ensure_pil()
            img = Image.open(image_path)
            orig_size = img.size

            max_width = 1280
            if img.width > max_width:
                ratio = max_width / img.width
                img = img.resize(
                    (max_width, int(img.height * ratio)),
                    Image.Resampling.LANCZOS,
                )

            # Convert to numpy array for EasyOCR
            np = _ensure_numpy()
            img_array = np.array(img)

            # Run OCR
            ocr = self._get_ocr()
            # EasyOCR returns list of [bbox, text, confidence]
            raw_results = ocr.readtext(img_array)

            # Parse results
            text_lines = []
            confidences = []

            for (bbox, text, confidence) in raw_results:
                if text and text.strip():
                    text_lines.append(text.strip())
                    confidences.append(confidence)

            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            full_text = "\n".join(text_lines)

            ocr_result = OCRResult(
                text_lines=text_lines,
                full_text=full_text,
                line_count=len(text_lines),
                confidence_avg=avg_confidence,
                read_time_ms=(time.monotonic() - start_time) * 1000,
                image_size=orig_size,
            )

            self._last_result = ocr_result

            logger.debug(
                "OCR read: %d lines, %.1f%% avg confidence, %.0fms — %s",
                ocr_result.line_count,
                ocr_result.confidence_avg * 100,
                ocr_result.read_time_ms,
                full_text[:80] if full_text else "(empty)",
            )

            return ocr_result

        except Exception as e:
            logger.debug("OCR read failed: %s", e)
            return OCRResult(read_time_ms=(time.monotonic() - start_time) * 1000)

    def read_image_array(self, img_array) -> OCRResult:
        """Extract text from a numpy image array.

        Args:
            img_array: numpy array (H, W, 3) in RGB format.

        Returns:
            OCRResult with extracted text lines and metadata.
        """
        if not self.is_available():
            return OCRResult()

        start_time = time.monotonic()

        try:
            # Downscale if too wide
            np = _ensure_numpy()
            if img_array.shape[1] > 1280:
                from PIL import Image as PILImage
                ratio = 1280 / img_array.shape[1]
                new_h = int(img_array.shape[0] * ratio)
                pil_img = PILImage.fromarray(img_array)
                pil_img = pil_img.resize((1280, new_h), PILImage.Resampling.LANCZOS)
                img_array = np.array(pil_img)

            ocr = self._get_ocr()
            raw_results = ocr.readtext(img_array)

            text_lines = []
            confidences = []

            for (bbox, text, confidence) in raw_results:
                if text and text.strip():
                    text_lines.append(text.strip())
                    confidences.append(confidence)

            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            full_text = "\n".join(text_lines)

            return OCRResult(
                text_lines=text_lines,
                full_text=full_text,
                line_count=len(text_lines),
                confidence_avg=avg_confidence,
                read_time_ms=(time.monotonic() - start_time) * 1000,
                image_size=(img_array.shape[1], img_array.shape[0]),
            )

        except Exception as e:
            logger.debug("OCR array read failed: %s", e)
            return OCRResult(read_time_ms=(time.monotonic() - start_time) * 1000)

    def get_last_result(self) -> OCRResult | None:
        """Get the most recently read OCR result without re-reading."""
        return self._last_result
