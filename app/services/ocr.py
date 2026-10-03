"""OCR and document text extraction service for JourneyBrief.

Provides local OCR processing using Tesseract/PyMuPDF for:
- Scanned PDF documents (page rendering to raster image -> OCR)
- Photographed / scanned image files (PNG, JPG, JPEG)
- Direct text extraction for clean text PDFs (bypasses OCR for efficiency)

STRICT BOUNDARIES:
- Transcription and technical text extraction only.
- OCR confidence is strictly technical confidence in optical character recognition.
- OCR confidence != LLM extraction confidence != clinical correctness.
- Tamil language support is explicitly verified against local tessdata; never faked.
"""

import json
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field
import pymupdf
import pytesseract

from app.core.config import settings
from app.services.document_ingestion import DocumentClassification, DocumentIngestionService
from app.services.document_quality import DocumentQualityChecker, QualityStatus


class OCRPageResult(BaseModel):
    """Structured OCR / text output for an individual document page."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(..., description="Document identifier")
    file_name: str = Field(..., description="Original file name")
    page_number: int = Field(..., ge=1, description="1-indexed page number")
    text: str = Field(..., description="Extracted or OCR-transcribed text")
    ocr_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Average optical character recognition confidence (technical only)",
    )
    ocr_confidence_min: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Minimum word-level OCR confidence on page",
    )
    language: str = Field(default="eng", description="OCR language(s) configured")


class OCRDocumentResult(BaseModel):
    """Aggregate document OCR result across all pages."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    file_name: str
    pages_processed: int
    classification: str
    ocr_used: bool
    average_ocr_confidence: Optional[float] = None
    min_ocr_confidence: Optional[float] = None
    pages: List[OCRPageResult] = Field(default_factory=list)
    status: str = Field(default="success", description="'success', 'needs_review', or 'unreadable'")
    reason: Optional[str] = Field(default=None, description="Explanation if status is not success")


class OCREngine:
    """Orchestrates local document text and OCR extraction."""

    DEFAULT_TESSERACT_CANDIDATES = [
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ]

    def __init__(
        self,
        tesseract_cmd: Optional[str] = None,
        default_languages: Optional[str] = None,
        output_dir: Path = Path("data/ocr"),
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.default_languages = default_languages or settings.OCR_LANGUAGES or "eng"
        self.ingestion_service = DocumentIngestionService()
        self.quality_checker = DocumentQualityChecker()

        # Resolve Tesseract binary path
        resolved_cmd = tesseract_cmd or settings.TESSERACT_CMD
        if resolved_cmd and not Path(resolved_cmd).is_file():
            resolved_cmd = None

        if not resolved_cmd:
            for cand in self.DEFAULT_TESSERACT_CANDIDATES:
                if cand.is_file():
                    resolved_cmd = str(cand)
                    break
            if not resolved_cmd:
                resolved_cmd = shutil.which("tesseract")

        if resolved_cmd and (Path(resolved_cmd).is_file() or shutil.which(resolved_cmd)):
            pytesseract.pytesseract.tesseract_cmd = resolved_cmd
            self.tesseract_cmd = resolved_cmd
        else:
            self.tesseract_cmd = None

    def is_tesseract_available(self) -> bool:
        """Check if a valid Tesseract executable is found."""
        if not self.tesseract_cmd:
            return False
        return Path(self.tesseract_cmd).is_file() or shutil.which(self.tesseract_cmd) is not None

    def get_available_languages(self) -> List[str]:
        """Return list of language packs physically installed in local Tesseract."""
        if not self.is_tesseract_available():
            return []
        try:
            return pytesseract.get_languages()
        except Exception:
            return ["eng"]

    def is_language_installed(self, lang_code: str) -> bool:
        """Check whether specific language (e.g. 'tam' or 'eng') is available."""
        available = self.get_available_languages()
        return lang_code.lower() in [l.lower() for l in available]

    def validate_languages(self, languages: str) -> Tuple[bool, str]:
        """Validate whether all requested languages are supported by local installation."""
        if not self.is_tesseract_available():
            return False, "Tesseract OCR engine is not installed or not found on PATH."

        installed = [l.lower() for l in self.get_available_languages()]
        requested = [l.strip().lower() for l in languages.split("+") if l.strip()]

        for req in requested:
            if req not in installed:
                if req == "tam":
                    return (
                        False,
                        "Tamil OCR requires installation of the appropriate Tesseract "
                        "language pack (tessdata/tam.traineddata).",
                    )
                return False, f"Tesseract language pack '{req}' is not installed."

        return True, "Languages available"

    def ocr_image(
        self,
        image: Image.Image,
        document_id: str,
        file_name: str,
        page_number: int = 1,
        languages: Optional[str] = None,
    ) -> OCRPageResult:
        """Run OCR on a PIL image and calculate technical optical confidence."""
        langs = languages or self.default_languages
        is_valid, msg = self.validate_languages(langs)
        if not is_valid:
            raise RuntimeError(f"OCR language error: {msg}")

        # Extract text and optical character data
        data = pytesseract.image_to_data(image, lang=langs, output_type=pytesseract.Output.DICT)
        text = pytesseract.image_to_string(image, lang=langs).strip()

        # Parse word-level confidences (conf >= 0; negative values indicate block dividers)
        valid_confs = [float(c) for c in data.get("conf", []) if float(c) >= 0]

        if valid_confs:
            avg_conf = sum(valid_confs) / len(valid_confs) / 100.0
            min_conf = min(valid_confs) / 100.0
        else:
            avg_conf = 0.0
            min_conf = 0.0

        avg_conf = max(0.0, min(1.0, avg_conf))
        min_conf = max(0.0, min(1.0, min_conf))

        return OCRPageResult(
            document_id=document_id,
            file_name=file_name,
            page_number=page_number,
            text=text,
            ocr_confidence=round(avg_conf, 3),
            ocr_confidence_min=round(min_conf, 3),
            language=langs,
        )

    def process_document(
        self,
        file_path: Path | str,
        document_id: Optional[str] = None,
        languages: Optional[str] = None,
    ) -> OCRDocumentResult:
        """Process document using intelligent routing (TEXT_PDF vs SCANNED_PDF vs IMAGE).

        - TEXT_PDF: PyMuPDF direct extraction (fast path, clean-PDF unchanged).
        - SCANNED_PDF: PyMuPDF page rendering to image -> Tesseract OCR.
        - IMAGE: PIL image -> Tesseract OCR.
        """
        path = Path(file_path)
        ingest_res = self.ingestion_service.ingest(path, document_id=document_id)
        doc_id = ingest_res.document_id
        fname = ingest_res.file_name

        if not ingest_res.is_supported:
            return OCRDocumentResult(
                document_id=doc_id,
                file_name=fname,
                pages_processed=0,
                classification=ingest_res.classification.value,
                ocr_used=False,
                status="unreadable",
                reason=ingest_res.details.get("reason", "Unsupported file type."),
            )

        page_results: List[OCRPageResult] = []

        # -------------------------------------------------------------
        # ROUTE A: TEXT_PDF (Direct PyMuPDF fast path, unchanged)
        # -------------------------------------------------------------
        if ingest_res.classification == DocumentClassification.TEXT_PDF:
            pdf_doc = pymupdf.open(str(path))
            for idx in range(len(pdf_doc)):
                page = pdf_doc[idx]
                text = page.get_text().strip()
                page_results.append(
                    OCRPageResult(
                        document_id=doc_id,
                        file_name=fname,
                        page_number=idx + 1,
                        text=text,
                        ocr_confidence=1.0,       # Native digital text has perfect optical fidelity
                        ocr_confidence_min=1.0,
                        language="eng",
                    )
                )
            pdf_doc.close()

            doc_result = OCRDocumentResult(
                document_id=doc_id,
                file_name=fname,
                pages_processed=len(page_results),
                classification=ingest_res.classification.value,
                ocr_used=False,
                average_ocr_confidence=1.0,
                min_ocr_confidence=1.0,
                pages=page_results,
                status="success",
            )
            self._save_ocr_output(doc_result)
            return doc_result

        # -------------------------------------------------------------
        # ROUTE B: SCANNED_PDF (Render pages to raster images -> OCR)
        # -------------------------------------------------------------
        if ingest_res.classification == DocumentClassification.SCANNED_PDF:
            pdf_doc = pymupdf.open(str(path))
            confs: List[float] = []
            min_confs: List[float] = []

            for idx in range(len(pdf_doc)):
                page = pdf_doc[idx]
                # Render page at 200 DPI for reliable OCR
                pix = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                page_res = self.ocr_image(
                    image=img,
                    document_id=doc_id,
                    file_name=fname,
                    page_number=idx + 1,
                    languages=languages,
                )
                page_results.append(page_res)
                confs.append(page_res.ocr_confidence)
                min_confs.append(page_res.ocr_confidence_min)

            pdf_doc.close()

            avg_c = (sum(confs) / len(confs)) if confs else 0.0
            min_c = min(min_confs) if min_confs else 0.0

            # Error handling for empty or unreadable OCR
            total_text_len = sum(len(p.text.strip()) for p in page_results)
            if total_text_len < 10:
                doc_result = OCRDocumentResult(
                    document_id=doc_id,
                    file_name=fname,
                    pages_processed=len(page_results),
                    classification=ingest_res.classification.value,
                    ocr_used=True,
                    average_ocr_confidence=round(avg_c, 3),
                    min_ocr_confidence=round(min_c, 3),
                    pages=page_results,
                    status="needs_review",
                    reason="OCR produced insufficient text",
                )
            else:
                doc_result = OCRDocumentResult(
                    document_id=doc_id,
                    file_name=fname,
                    pages_processed=len(page_results),
                    classification=ingest_res.classification.value,
                    ocr_used=True,
                    average_ocr_confidence=round(avg_c, 3),
                    min_ocr_confidence=round(min_c, 3),
                    pages=page_results,
                    status="success",
                )

            self._save_ocr_output(doc_result)
            return doc_result

        # -------------------------------------------------------------
        # ROUTE C: IMAGE (PNG, JPG, JPEG -> OCR)
        # -------------------------------------------------------------
        if ingest_res.classification == DocumentClassification.IMAGE:
            with Image.open(path) as img:
                rgb_img = img.convert("RGB")
                page_res = self.ocr_image(
                    image=rgb_img,
                    document_id=doc_id,
                    file_name=fname,
                    page_number=1,
                    languages=languages,
                )
                page_results.append(page_res)

            text_len = len(page_res.text.strip())
            if text_len < 10:
                status = "needs_review"
                reason = "OCR produced insufficient text"
            else:
                status = "success"
                reason = None

            doc_result = OCRDocumentResult(
                document_id=doc_id,
                file_name=fname,
                pages_processed=1,
                classification=ingest_res.classification.value,
                ocr_used=True,
                average_ocr_confidence=page_res.ocr_confidence,
                min_ocr_confidence=page_res.ocr_confidence_min,
                pages=page_results,
                status=status,
                reason=reason,
            )
            self._save_ocr_output(doc_result)
            return doc_result

        return OCRDocumentResult(
            document_id=doc_id,
            file_name=fname,
            pages_processed=0,
            classification="UNKNOWN",
            ocr_used=False,
            status="unreadable",
            reason="Unrecognized classification state",
        )

    def _save_ocr_output(self, result: OCRDocumentResult) -> None:
        """Persist structured OCR result to data/ocr/ in JSON format."""
        out_path = self.output_dir / f"{result.document_id}.json"
        out_path.write_text(
            json.dumps(result.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
