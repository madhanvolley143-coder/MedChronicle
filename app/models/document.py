from datetime import date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class DocumentType(str, Enum):
    """Allowed clinical document types in the patient record archive."""

    VISIT_NOTE = "visit_note"
    PATHOLOGY_REPORT = "pathology_report"
    LABORATORY_REPORT = "laboratory_report"
    IMAGING_REPORT = "imaging_report"
    PRESCRIPTION = "prescription"
    DISCHARGE_SUMMARY = "discharge_summary"
    REFERRAL_LETTER = "referral_letter"
    PROCEDURE_NOTE = "procedure_note"
    OTHER = "other"


class Document(BaseModel):
    """Metadata for a synthetic patient document."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(..., min_length=1, description="Unique identifier for the document")
    file_name: str = Field(..., min_length=1, description="File name of the document")
    document_type: DocumentType = Field(..., description="Categorized document type")
    document_date: Optional[date] = Field(default=None, description="Document date in ISO format if documented")
    page_count: Optional[int] = Field(default=None, ge=1, description="Total number of pages (must be >= 1)")
