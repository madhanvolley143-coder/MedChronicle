"""Document ingestion service for JourneyBrief.

Accepts medical document files (clean PDFs, scanned PDFs, photographed documents, images),
identifies technical file attributes, and classifies documents for appropriate extraction routing.

STRICT BOUNDARY:
- Technical file inspection only.
- No clinical interpretation or medical reasoning.
"""

from enum import Enum
import os
from pathlib import Path
from typing import Any, Dict, Optional
import pymupdf  # PyMuPDF
from pydantic import BaseModel, ConfigDict, Field


class DocumentClassification(str, Enum):
    """Routing classification for ingested document."""
    TEXT_PDF = "TEXT_PDF"
    SCANNED_PDF = "SCANNED_PDF"
    IMAGE = "IMAGE"
    UNSUPPORTED = "UNSUPPORTED"


class IngestionResult(BaseModel):
    """Technical summary and routing recommendation for ingested document."""

    model_config = ConfigDict(extra="forbid")

    file_name: str
    file_path: str
    file_size_bytes: int
    file_extension: str
    document_id: str
    classification: DocumentClassification
    page_count: int
    has_selectable_text: bool
    is_supported: bool
    details: Dict[str, Any] = Field(default_factory=dict)


class DocumentIngestionService:
    """Classifies document files and extracts technical structural metadata."""

    SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
    PROHIBITED_EXTENSIONS = {
        ".exe", ".bat", ".cmd", ".sh", ".py", ".js", ".vbs", ".ps1", ".dll", ".bin",
    }

    # Minimum characters of selectable text per page to classify as text PDF
    MIN_SELECTABLE_CHARS_PER_PAGE = 35

    def __init__(self) -> None:
        pass

    def ingest(
        self,
        file_path: Path | str,
        document_id: Optional[str] = None,
    ) -> IngestionResult:
        """Inspect and classify an incoming document file.

        Args:
            file_path: Path to the target document.
            document_id: Optional identifier; generated from filename stem if not supplied.

        Returns:
            IngestionResult containing technical classification and page information.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Document file not found at: {path}")

        file_size = os.path.getsize(path)
        ext = path.suffix.lower()
        fname = path.name

        doc_id = document_id or path.stem.split("_")[0]
        if not doc_id:
            doc_id = path.stem

        # 1. Check for unsupported or executable files
        if ext in self.PROHIBITED_EXTENSIONS or ext not in self.SUPPORTED_EXTENSIONS:
            return IngestionResult(
                file_name=fname,
                file_path=str(path.resolve()),
                file_size_bytes=file_size,
                file_extension=ext,
                document_id=doc_id,
                classification=DocumentClassification.UNSUPPORTED,
                page_count=0,
                has_selectable_text=False,
                is_supported=False,
                details={"reason": f"File extension '{ext}' is unsupported or prohibited."},
            )

        # 2. Check Images (PNG, JPG, JPEG)
        if ext in {".png", ".jpg", ".jpeg"}:
            return IngestionResult(
                file_name=fname,
                file_path=str(path.resolve()),
                file_size_bytes=file_size,
                file_extension=ext,
                document_id=doc_id,
                classification=DocumentClassification.IMAGE,
                page_count=1,
                has_selectable_text=False,
                is_supported=True,
                details={"mime_type": f"image/{'jpeg' if ext in ('.jpg', '.jpeg') else 'png'}"},
            )

        # 3. Check PDF documents
        try:
            pdf_doc = pymupdf.open(str(path))
            page_count = len(pdf_doc)
            total_chars = 0
            page_char_counts = []

            for page_idx in range(page_count):
                page = pdf_doc[page_idx]
                text = page.get_text().strip()
                char_count = len(text)
                total_chars += char_count
                page_char_counts.append(char_count)

            pdf_doc.close()

            # Determine whether PDF has meaningful selectable text
            avg_chars = (total_chars / page_count) if page_count > 0 else 0
            has_selectable = avg_chars >= self.MIN_SELECTABLE_CHARS_PER_PAGE

            classification = (
                DocumentClassification.TEXT_PDF
                if has_selectable
                else DocumentClassification.SCANNED_PDF
            )

            return IngestionResult(
                file_name=fname,
                file_path=str(path.resolve()),
                file_size_bytes=file_size,
                file_extension=ext,
                document_id=doc_id,
                classification=classification,
                page_count=page_count,
                has_selectable_text=has_selectable,
                is_supported=True,
                details={
                    "total_selectable_characters": total_chars,
                    "avg_characters_per_page": round(avg_chars, 1),
                    "page_character_counts": page_char_counts,
                },
            )

        except Exception as exc:
            return IngestionResult(
                file_name=fname,
                file_path=str(path.resolve()),
                file_size_bytes=file_size,
                file_extension=ext,
                document_id=doc_id,
                classification=DocumentClassification.UNSUPPORTED,
                page_count=0,
                has_selectable_text=False,
                is_supported=False,
                details={"error": f"Failed to parse PDF: {str(exc)}"},
            )
