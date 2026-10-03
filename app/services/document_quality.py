"""Document technical quality assessment service for JourneyBrief.

Checks document image resolution, page orientation, text density, and OCR confidence.

STRICT SAFETY BOUNDARY:
- Technical document quality assessment ONLY.
- Absolutely NO clinical interpretation or clinical threat terminology.
- Never use terms such as: 'clinical risk', 'patient risk', 'diagnosis', 'severity',
  'treatment failure', 'unreliable patient data'.
- All issues are phrased neutrally as technical scanning/image issues.
"""

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from PIL import Image, ImageStat
from pydantic import BaseModel, ConfigDict, Field
import pymupdf


class QualityStatus(str, Enum):
    """Technical quality status of the document."""
    GOOD = "good"
    NEEDS_REVIEW = "needs_review"
    UNREADABLE = "unreadable"


class QualityReport(BaseModel):
    """Structured report on technical document and OCR quality."""

    model_config = ConfigDict(extra="forbid")

    status: QualityStatus = Field(..., description="'good', 'needs_review', or 'unreadable'")
    issues: List[str] = Field(default_factory=list, description="Technical quality issues found")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Technical measurements")


class DocumentQualityChecker:
    """Evaluates technical scan quality, text density, and image readability."""

    MIN_IMAGE_DIMENSION = 300  # pixels
    MIN_TEXT_CHAR_COUNT = 30   # minimum characters for non-empty page
    MIN_OCR_CONFIDENCE_THRESHOLD = 0.60  # average OCR confidence below this flags needs_review
    UNREADABLE_OCR_CONFIDENCE_THRESHOLD = 0.25

    def __init__(self) -> None:
        pass

    def check_image_file(
        self,
        image_path: Path | str,
        page_number: int = 1,
    ) -> QualityReport:
        """Inspect an image file for resolution, blankness, and technical readability."""
        path = Path(image_path)
        issues: List[str] = []
        metrics: Dict[str, Any] = {}

        try:
            with Image.open(path) as img:
                width, height = img.size
                metrics["width"] = width
                metrics["height"] = height
                metrics["format"] = img.format

                # 1. Resolution check
                if width < self.MIN_IMAGE_DIMENSION or height < self.MIN_IMAGE_DIMENSION:
                    issues.append(
                        f"Page {page_number} has low image resolution ({width}x{height} px). "
                        "Text may be difficult to read."
                    )

                # 2. Blank page check using image variance
                gray = img.convert("L")
                stat = ImageStat.Stat(gray)
                var = stat.var[0] if stat.var else 0.0
                metrics["grayscale_variance"] = round(var, 2)

                if var < 5.0:
                    issues.append(f"Page {page_number} appears blank or has virtually no visual contrast.")

        except Exception as exc:
            issues.append(f"Failed to inspect image file: {str(exc)}")
            return QualityReport(
                status=QualityStatus.UNREADABLE,
                issues=issues,
                metrics=metrics,
            )

        status = self._evaluate_status(issues, metrics)
        return QualityReport(status=status, issues=issues, metrics=metrics)

    def check_ocr_text(
        self,
        text: str,
        ocr_confidence: Optional[float] = None,
        page_number: int = 1,
    ) -> QualityReport:
        """Assess technical quality of extracted or OCR-transcribed text."""
        issues: List[str] = []
        metrics: Dict[str, Any] = {}

        clean_text = text.strip() if text else ""
        char_count = len(clean_text)
        word_count = len(clean_text.split()) if clean_text else 0

        metrics["character_count"] = char_count
        metrics["word_count"] = word_count
        if ocr_confidence is not None:
            metrics["ocr_confidence"] = round(ocr_confidence, 3)

        # 1. Empty or very low text density
        if char_count == 0:
            issues.append(f"Page {page_number} contains no readable text output.")
        elif char_count < self.MIN_TEXT_CHAR_COUNT:
            issues.append(
                f"Page {page_number} has extremely low text density ({char_count} characters). "
                "Document may be incomplete or poorly scanned."
            )

        # 2. OCR confidence evaluation
        if ocr_confidence is not None:
            if ocr_confidence < self.UNREADABLE_OCR_CONFIDENCE_THRESHOLD:
                issues.append(
                    f"Page {page_number} has very low OCR confidence ({round(ocr_confidence * 100, 1)}%). "
                    "Text transcription may contain errors."
                )
            elif ocr_confidence < self.MIN_OCR_CONFIDENCE_THRESHOLD:
                issues.append(
                    f"Page {page_number} has suboptimal OCR confidence ({round(ocr_confidence * 100, 1)}%)."
                )

        status = self._evaluate_status(issues, metrics)
        return QualityReport(status=status, issues=issues, metrics=metrics)

    def check_pdf(self, pdf_path: Path | str) -> QualityReport:
        """Check PDF pages for technical orientation, blankness, and readability."""
        path = Path(pdf_path)
        issues: List[str] = []
        metrics: Dict[str, Any] = {}

        try:
            doc = pymupdf.open(str(path))
            metrics["page_count"] = len(doc)
            total_chars = 0

            for idx, page in enumerate(doc, start=1):
                # Orientation / rotation check
                if page.rotation != 0:
                    issues.append(f"Page {idx} is rotated by {page.rotation} degrees.")

                text = page.get_text().strip()
                total_chars += len(text)

            doc.close()
            metrics["total_characters"] = total_chars

            if total_chars == 0:
                issues.append("Document contains no selectable text (scanned raster PDF).")

        except Exception as exc:
            issues.append(f"Failed to inspect PDF: {str(exc)}")
            return QualityReport(
                status=QualityStatus.UNREADABLE,
                issues=issues,
                metrics=metrics,
            )

        status = self._evaluate_status(issues, metrics)
        return QualityReport(status=status, issues=issues, metrics=metrics)

    def _evaluate_status(self, issues: List[str], metrics: Dict[str, Any]) -> QualityStatus:
        """Determine overall quality status based strictly on technical findings."""
        if not issues:
            return QualityStatus.GOOD

        # Unreadable if blank, zero readable text, or extreme failure
        for issue in issues:
            lowered = issue.lower()
            if "appears blank" in lowered or "no readable text" in lowered or "very low ocr confidence" in lowered:
                return QualityStatus.UNREADABLE

        return QualityStatus.NEEDS_REVIEW
