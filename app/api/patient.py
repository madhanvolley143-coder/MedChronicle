"""Patient and doctor consultation readiness API routes for JourneyBrief.

Provides endpoints to retrieve:
- Deterministic JourneyBrief summary
- Patient chronological timeline
- Documented changes
- Documentation / information flags
- Source PDF documents
- Doctor review state and verification updates
"""

from pathlib import Path
from typing import List, Optional, Tuple
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from app.models.review import DoctorReview, ReviewUpdateRequest
from app.services.change_detector import ChangeDetector, PatientChanges
from app.services.document_ingestion import DocumentClassification, DocumentIngestionService
from app.services.document_quality import DocumentQualityChecker
from app.services.flag_detector import FlagDetector, PatientFlags
from app.services.journey_brief import JourneyBrief, JourneyBriefGenerator
from app.services.ocr import OCREngine
from app.services.pipeline_coordinator import (
    BatchProcessingReport,
    BatchUploadSummary,
    PipelineCoordinator,
    SingleDocumentResult,
)
from app.services.review_service import ReviewService
from app.services.timeline import PatientTimeline, TimelineEngine

router = APIRouter(prefix="/api/patient", tags=["patient"])

# Recognized synthetic patients for the prototype
KNOWN_PATIENT_IDS = {
    "syn-cancer-001",
    "syn_cancer_001",
    "patient_001",
    "patient-001",
}

STRUCTURED_DIR = Path("data/structured")
EXTRACTED_DIR = Path("data/extracted")
DOCUMENTS_DIR = Path("data/documents")
REVIEWS_DIR = Path("data/reviews")


def _validate_patient_id(patient_id: str) -> str:
    """Validate that the patient ID is recognized; normalize if appropriate."""
    normalized = patient_id.strip().lower()
    if normalized not in KNOWN_PATIENT_IDS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient '{patient_id}' not found in records.",
        )
    return "SYN-CANCER-001"


def _resolve_document_file(document_id: str) -> Path:
    """Resolve a document ID to its physical PDF file path."""
    clean_id = document_id.strip()
    if not DOCUMENTS_DIR.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source documents directory not found.",
        )

    # 1. Exact file match
    exact = DOCUMENTS_DIR / clean_id
    if exact.is_file():
        return exact

    # 1b. Exact file match with common extensions
    for ext in (".pdf", ".png", ".jpg", ".jpeg"):
        exact_ext = DOCUMENTS_DIR / f"{clean_id}{ext}"
        if exact_ext.is_file():
            return exact_ext

    # 2. Prefix match (e.g. doc-001 -> doc-001_visit_note_2026-01-05.pdf or 01 -> 01_2026-01-05_consultation_note.pdf)
    id_without_ext = clean_id
    for ext in (".pdf", ".png", ".jpg", ".jpeg"):
        if clean_id.lower().endswith(ext):
            id_without_ext = clean_id[:-len(ext)]
            break

    candidates = list(DOCUMENTS_DIR.glob(f"{id_without_ext}*"))
    for c in candidates:
        if c.is_file() and c.suffix.lower() in (".pdf", ".png", ".jpg", ".jpeg"):
            return c

    # 3. Check uploads directory
    uploads_dir = Path("data/messy_documents/uploads")
    if uploads_dir.is_dir():
        exact_up = uploads_dir / clean_id
        if exact_up.is_file():
            return exact_up
        for c in uploads_dir.glob(f"{id_without_ext}*"):
            if c.is_file() and c.suffix.lower() in (".pdf", ".png", ".jpg", ".jpeg"):
                return c

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Document '{document_id}' not found.",
    )


@router.get("/{patient_id}/brief", response_model=JourneyBrief)
def get_patient_brief(patient_id: str) -> JourneyBrief:
    """Retrieve the deterministic source-linked JourneyBrief for a patient."""
    canonical_id = _validate_patient_id(patient_id)
    generator = JourneyBriefGenerator(
        structured_dir=STRUCTURED_DIR,
        extracted_dir=EXTRACTED_DIR,
    )
    return generator.generate_brief(patient_id=canonical_id)


@router.get("/{patient_id}/timeline", response_model=PatientTimeline)
def get_patient_timeline(patient_id: str) -> PatientTimeline:
    """Retrieve the complete chronological timeline for a patient."""
    canonical_id = _validate_patient_id(patient_id)
    engine = TimelineEngine(structured_dir=STRUCTURED_DIR)
    return engine.build_timeline(patient_id=canonical_id)


@router.get("/{patient_id}/changes", response_model=PatientChanges)
def get_patient_changes(patient_id: str) -> PatientChanges:
    """Retrieve documented clinical comparisons and changes across documents."""
    canonical_id = _validate_patient_id(patient_id)
    detector = ChangeDetector(structured_dir=STRUCTURED_DIR)
    return detector.detect_changes(patient_id=canonical_id)


@router.get("/{patient_id}/flags", response_model=PatientFlags)
def get_patient_flags(patient_id: str) -> PatientFlags:
    """Retrieve documentation and information flags (pending tests, conflicts)."""
    canonical_id = _validate_patient_id(patient_id)
    detector = FlagDetector(structured_dir=STRUCTURED_DIR)
    return detector.detect_flags(patient_id=canonical_id)


@router.get("/{patient_id}/documents/{document_id}")
def get_patient_document(
    patient_id: str,
    document_id: str,
    page: Optional[int] = Query(default=None, description="Optional page number"),
):
    """Retrieve original source document (PDF or image)."""
    _validate_patient_id(patient_id)
    doc_path = _resolve_document_file(document_id)

    ext = doc_path.suffix.lower()
    media_type = "application/pdf"
    if ext == ".png":
        media_type = "image/png"
    elif ext in (".jpg", ".jpeg"):
        media_type = "image/jpeg"

    headers = {
        "Content-Disposition": f'inline; filename="{doc_path.name}"',
        "X-Document-ID": document_id,
    }
    if page:
        headers["X-Page-Number"] = str(page)

    return FileResponse(
        path=doc_path,
        media_type=media_type,
        filename=doc_path.name,
        headers=headers,
    )


@router.get("/{patient_id}/review", response_model=DoctorReview)
def get_patient_review(patient_id: str) -> DoctorReview:
    """Retrieve clinician review status and item verifications."""
    canonical_id = _validate_patient_id(patient_id)
    service = ReviewService(reviews_dir=REVIEWS_DIR)
    return service.get_review(patient_id=canonical_id)


@router.post("/{patient_id}/review", response_model=DoctorReview)
def update_patient_review(
    patient_id: str,
    update: ReviewUpdateRequest,
) -> DoctorReview:
    """Update clinician review status, notes, or mark individual items verified."""
    canonical_id = _validate_patient_id(patient_id)
    service = ReviewService(reviews_dir=REVIEWS_DIR)
    return service.update_review(patient_id=canonical_id, update=update)


class UploadDocumentResponse(BaseModel):
    """Technical summary response for uploaded document ingestion."""

    model_config = ConfigDict(extra="ignore")

    patient_id: str
    document_id: str
    file_name: str
    file_size_bytes: int
    classification: str
    is_supported: bool
    page_count: int
    ocr_used: bool
    ocr_confidence: Optional[float] = None
    quality_status: str
    quality_issues: List[str] = Field(default_factory=list)
    technical_status: str = Field(..., description="'success', 'needs_review', or 'failed'")
    message: str

    summary: Optional[BatchUploadSummary] = None
    documents: List[SingleDocumentResult] = Field(default_factory=list)
    artifacts_regenerated: bool = False
    processing_time_seconds: Optional[float] = None


class ResetDemoResponse(BaseModel):
    """Response returned after resetting synthetic demonstration environment."""

    model_config = ConfigDict(extra="forbid")

    patient_id: str
    status: str
    message: str


@router.post("/{patient_id}/documents/upload", response_model=UploadDocumentResponse)
async def upload_patient_documents(
    patient_id: str,
    files: Optional[List[UploadFile]] = File(default=None),
    file: Optional[UploadFile] = File(default=None),
) -> UploadDocumentResponse:
    """Accept and ingest one or multiple supported PDF or image documents.

    Performs technical quality checks, conditional OCR transcription, structured fact
    extraction, and automatic downstream artifact regeneration (Timeline, Changes, Flags, Brief).
    """
    canonical_id = _validate_patient_id(patient_id)

    # 1. Consolidate incoming files
    incoming_files: List[UploadFile] = []
    if files:
        incoming_files.extend(files)
    if file:
        incoming_files.append(file)

    if not incoming_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No document files provided for upload.",
        )

    # 2. Check extensions for single-file upload requests to maintain strict validation
    ingestion_service = DocumentIngestionService()
    if len(incoming_files) == 1:
        fname = incoming_files[0].filename or "document"
        ext = Path(fname).suffix.lower()
        if ext not in ingestion_service.SUPPORTED_EXTENSIONS or ext in ingestion_service.PROHIBITED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension '{ext}' is unsupported. Only PDF, PNG, JPG, and JPEG are allowed.",
            )

    # 3. Read content
    file_tuples: List[Tuple[str, bytes]] = []
    for f in incoming_files:
        original_fname = f.filename or "uploaded_document"
        content = await f.read()
        file_tuples.append((original_fname, content))

    # 4. Process multi-document batch through PipelineCoordinator
    coordinator = PipelineCoordinator(
        structured_dir=STRUCTURED_DIR,
        documents_dir=DOCUMENTS_DIR,
        uploads_dir=Path("data/messy_documents/uploads"),
        timeline_dir=Path("data/timeline"),
        changes_dir=Path("data/changes"),
        flags_dir=Path("data/flags"),
        brief_dir=Path("data/brief"),
    )
    batch_report = coordinator.process_batch(file_tuples, patient_id=canonical_id)

    # 5. Populate response
    primary = batch_report.documents[0] if batch_report.documents else None

    return UploadDocumentResponse(
        patient_id=canonical_id,
        document_id=primary.document_id if primary else "unknown",
        file_name=primary.file_name if primary else "unknown",
        file_size_bytes=primary.file_size_bytes if primary else 0,
        classification=primary.classification if primary else "UNKNOWN",
        is_supported=primary.is_supported if primary else False,
        page_count=primary.page_count if primary else 0,
        ocr_used=primary.ocr_used if primary else False,
        ocr_confidence=primary.ocr_confidence if primary else None,
        quality_status=primary.quality_status if primary else "unreadable",
        quality_issues=primary.quality_issues if primary else [],
        technical_status=primary.technical_status if primary else "failed",
        message=batch_report.message,
        summary=batch_report.summary,
        documents=batch_report.documents,
        artifacts_regenerated=batch_report.artifacts_regenerated,
        processing_time_seconds=batch_report.processing_time_seconds,
    )


@router.post("/{patient_id}/reset", response_model=ResetDemoResponse)
async def reset_demo_data(patient_id: str) -> ResetDemoResponse:
    """Safely restore the demo environment to its clean 10-document synthetic baseline.

    Removes any ad-hoc uploaded documents, clears temporary structured facts, resets
    doctor review records to pending, and regenerates all downstream brief artifacts.
    """
    canonical_id = _validate_patient_id(patient_id)
    coordinator = PipelineCoordinator(
        structured_dir=STRUCTURED_DIR,
        documents_dir=DOCUMENTS_DIR,
        uploads_dir=Path("data/messy_documents/uploads"),
        timeline_dir=Path("data/timeline"),
        changes_dir=Path("data/changes"),
        flags_dir=Path("data/flags"),
        brief_dir=Path("data/brief"),
    )
    coordinator.reset_demo_baseline(patient_id=canonical_id)
    return ResetDemoResponse(
        patient_id=canonical_id,
        status="ok",
        message="Demo data successfully reset to the 10-document synthetic baseline.",
    )

