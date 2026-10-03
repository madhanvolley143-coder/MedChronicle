"""PDF document reader service for JourneyBrief.

Extracts page-by-page text from medical PDF documents using PyMuPDF while
preserving document provenance, page counts, and 1-indexed page numbering.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    import pymupdf as fitz
except ImportError:
    import fitz


class DocumentReadError(Exception):
    """Raised when a document cannot be found, opened, or parsed."""


class PDFDocumentReader:
    """Service for deterministic text extraction from PDF files."""

    @staticmethod
    def extract_text(
        pdf_path: Union[str, Path],
        document_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extract text page-by-page from a PDF file.

        Args:
            pdf_path: Absolute or relative path to the PDF document.
            document_id: Optional document ID. If None, inferred from the filename
                         (e.g., 'doc-001_visit_note_2026-01-05.pdf' -> 'doc-001').

        Returns:
            Dict containing document metadata and page-level extracted text:
            {
                "document_id": str,
                "file_name": str,
                "page_count": int,
                "pages": [
                    {
                        "page_number": int (1-based),
                        "text": str
                    },
                    ...
                ]
            }

        Raises:
            FileNotFoundError: If the PDF path does not exist.
            DocumentReadError: If the PDF is corrupted or unreadable.
        """
        path = Path(pdf_path)
        if not path.is_file():
            raise FileNotFoundError(f"PDF document not found: {path}")

        file_name = path.name

        # Incur document_id if not provided
        if not document_id:
            # E.g. 'doc-001_visit_note_2026-01-05.pdf' -> 'doc-001'
            if "_" in file_name:
                document_id = file_name.split("_")[0]
            else:
                document_id = path.stem

        pages: List[Dict[str, Any]] = []

        try:
            with fitz.open(str(path)) as doc:
                page_count = len(doc)
                if page_count == 0:
                    raise DocumentReadError(f"PDF has 0 pages: {path}")

                for page_idx in range(page_count):
                    page = doc[page_idx]
                    raw_text = page.get_text("text")
                    # Preserve internal whitespace/newlines, strip only trailing edge whitespace
                    clean_text = raw_text.rstrip()

                    pages.append(
                        {
                            "page_number": page_idx + 1,
                            "text": clean_text,
                        }
                    )
        except Exception as exc:
            if isinstance(exc, DocumentReadError):
                raise
            raise DocumentReadError(f"Failed to read PDF document '{path}': {exc}") from exc

        return {
            "document_id": document_id,
            "file_name": file_name,
            "page_count": len(pages),
            "pages": pages,
        }


def extract_document_text(
    pdf_path: Union[str, Path],
    document_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Convenience function wrapping PDFDocumentReader.extract_text."""
    return PDFDocumentReader.extract_text(pdf_path=pdf_path, document_id=document_id)
