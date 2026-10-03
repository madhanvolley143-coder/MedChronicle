"""End-to-end pipeline coordinator for JourneyBrief document ingestion, OCR, extraction, and synthesis.

Orchestrates multi-document batch uploads:
1. Ingestion & classification (PDF, PNG, JPG, JPEG)
2. Technical quality checks
3. OCR processing (if scanned PDF or image)
4. Structured fact extraction & Pydantic validation
5. Deterministic artifact regeneration (Timeline, Changes, Flags, JourneyBrief)

STRICT SAFETY BOUNDARIES:
- Fully deterministic synthesis; Gemini is used ONLY for extraction.
- Technical quality issues are never described as medical risks.
- One failed document does not corrupt other successful documents.
"""

import json
import logging
from pathlib import Path
import shutil
import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field

from app.services.change_detector import ChangeDetector
from app.services.document_ingestion import DocumentClassification, DocumentIngestionService
from app.services.document_quality import DocumentQualityChecker, QualityStatus
from app.services.extractor import ExtractionService
from app.services.flag_detector import FlagDetector
from app.services.journey_brief import JourneyBriefGenerator
from app.services.ocr import OCREngine
from app.services.timeline import TimelineEngine

logger = logging.getLogger(__name__)


class SingleDocumentResult(BaseModel):
    """Detailed result for an individual ingested document."""

    model_config = ConfigDict(extra="forbid")

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
    facts_extracted_count: int = 0
    message: str


class BatchUploadSummary(BaseModel):
    """Aggregated processing summary for a multi-document upload action."""

    model_config = ConfigDict(extra="forbid")

    documents_received: int
    successfully_processed: int
    warnings: int
    failed: int
    processing_time_seconds: Optional[float] = None


class BatchProcessingReport(BaseModel):
    """Complete batch processing report returned to callers."""

    model_config = ConfigDict(extra="forbid")

    patient_id: str
    summary: BatchUploadSummary
    documents: List[SingleDocumentResult]
    artifacts_regenerated: bool = False
    message: str
    processing_time_seconds: Optional[float] = None


class PipelineCoordinator:
    """Coordinates end-to-end multi-document ingestion and deterministic synthesis."""

    def __init__(
        self,
        structured_dir: Path = Path("data/structured"),
        documents_dir: Path = Path("data/documents"),
        uploads_dir: Path = Path("data/messy_documents/uploads"),
        timeline_dir: Path = Path("data/timeline"),
        changes_dir: Path = Path("data/changes"),
        flags_dir: Path = Path("data/flags"),
        brief_dir: Path = Path("data/brief"),
        extractor: Optional[ExtractionService] = None,
    ) -> None:
        self.structured_dir = Path(structured_dir)
        self.documents_dir = Path(documents_dir)
        self.uploads_dir = Path(uploads_dir)
        self.timeline_dir = Path(timeline_dir)
        self.changes_dir = Path(changes_dir)
        self.flags_dir = Path(flags_dir)
        self.brief_dir = Path(brief_dir)

        self.structured_dir.mkdir(parents=True, exist_ok=True)
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)

        self.ingestion_service = DocumentIngestionService()
        self.quality_checker = DocumentQualityChecker()
        self.ocr_engine = OCREngine()
        self._custom_extractor = extractor

    def _get_extractor(self) -> ExtractionService:
        if self._custom_extractor is not None:
            return self._custom_extractor
        return ExtractionService()

    def process_file_content(
        self,
        file_name: str,
        content: bytes,
        patient_id: str = "SYN-CANCER-001",
    ) -> SingleDocumentResult:
        """Ingest, check, transcribe, and extract a single uploaded file."""
        file_size = len(content)
        ext = Path(file_name).suffix.lower()

        # 1. Extension validation
        if ext not in self.ingestion_service.SUPPORTED_EXTENSIONS or ext in self.ingestion_service.PROHIBITED_EXTENSIONS:
            return SingleDocumentResult(
                document_id="unsupported",
                file_name=file_name,
                file_size_bytes=file_size,
                classification=DocumentClassification.UNSUPPORTED.value,
                is_supported=False,
                page_count=0,
                ocr_used=False,
                quality_status=QualityStatus.UNREADABLE.value,
                quality_issues=[f"File extension '{ext}' is unsupported. Only PDF, PNG, JPG, JPEG allowed."],
                technical_status="failed",
                facts_extracted_count=0,
                message="Unsupported file type rejected.",
            )

        # 2. Save safely to uploads directory and documents directory
        target_path = self.uploads_dir / file_name
        target_path.write_bytes(content)

        # Copy to documents_dir so it can be viewed by the source viewer endpoint
        doc_store_path = self.documents_dir / file_name
        shutil.copyfile(target_path, doc_store_path)

        # 3. Technical ingestion classification
        ingest_res = self.ingestion_service.ingest(target_path)
        doc_id = ingest_res.document_id

        if not ingest_res.is_supported:
            return SingleDocumentResult(
                document_id=doc_id,
                file_name=file_name,
                file_size_bytes=file_size,
                classification=ingest_res.classification.value,
                is_supported=False,
                page_count=0,
                ocr_used=False,
                quality_status=QualityStatus.UNREADABLE.value,
                quality_issues=[ingest_res.details.get("reason", "Malformed or unsupported document content.")],
                technical_status="failed",
                facts_extracted_count=0,
                message="Document ingestion failed.",
            )

        # 4. OCR / Text extraction
        ocr_res = self.ocr_engine.process_document(target_path, document_id=doc_id)

        # 5. Technical Quality Checks
        quality_issues: List[str] = []
        if ingest_res.classification == DocumentClassification.IMAGE:
            q_rep = self.quality_checker.check_image_file(target_path)
            quality_issues.extend(q_rep.issues)
        elif ingest_res.classification in (DocumentClassification.TEXT_PDF, DocumentClassification.SCANNED_PDF):
            q_rep = self.quality_checker.check_pdf(target_path)
            quality_issues.extend(q_rep.issues)

        for page in ocr_res.pages:
            t_rep = self.quality_checker.check_ocr_text(
                page.text,
                ocr_confidence=page.ocr_confidence if ocr_res.ocr_used else None,
                page_number=page.page_number,
            )
            quality_issues.extend(t_rep.issues)

        # Determine technical status
        if ocr_res.status == "needs_review" or any("needs_review" in i.lower() for i in quality_issues):
            quality_status = QualityStatus.NEEDS_REVIEW.value
            tech_status = "needs_review"
        elif any("unreadable" in i.lower() or "blank" in i.lower() for i in quality_issues) or ocr_res.status == "unreadable":
            quality_status = QualityStatus.UNREADABLE.value
            tech_status = "needs_review"
        else:
            quality_status = QualityStatus.GOOD.value
            tech_status = "success"

        # 6. Structured extraction via ExtractionService
        extracted_facts_dict: Dict[str, List[Any]] = {
            "visits": [],
            "pathology_findings": [],
            "laboratory_results": [],
            "imaging_reports": [],
            "medications": [],
            "procedures": [],
            "referrals": [],
            "investigations": [],
            "timeline_events": [],
        }
        total_facts = 0

        # Only extract if page text is not empty
        has_readable_text = any(len(p.text.strip()) >= 10 for p in ocr_res.pages)
        if has_readable_text:
            try:
                extractor = self._get_extractor()
                for p in ocr_res.pages:
                    if len(p.text.strip()) < 10:
                        continue
                    page_facts = extractor.extract_page(
                        document_id=doc_id,
                        file_name=file_name,
                        page_number=p.page_number,
                        page_text=p.text,
                    )
                    for cat, facts in page_facts.items():
                        if cat in extracted_facts_dict:
                            extracted_facts_dict[cat].extend(facts)
                            total_facts += len(facts)
            except Exception as exc:
                logger.warning("Extraction warning for %s: %s", file_name, exc)
                quality_issues.append(f"Structured fact extraction encountered a non-fatal error: {str(exc)}")
                tech_status = "needs_review"

        # 7. Persist structured output to data/structured/{doc_id}.json
        # Convert Pydantic objects to dicts for clean JSON storage
        serializable_facts: Dict[str, List[Any]] = {}
        for cat, items in extracted_facts_dict.items():
            serializable_facts[cat] = [
                it.model_dump(mode="json") if hasattr(it, "model_dump") else it
                for it in items
            ]

        structured_record = {
            "document_id": doc_id,
            "file_name": file_name,
            "pages_processed": ingest_res.page_count,
            "facts": serializable_facts,
        }
        out_structured_file = self.structured_dir / f"{doc_id}.json"
        out_structured_file.write_text(json.dumps(structured_record, indent=2), encoding="utf-8")

        return SingleDocumentResult(
            document_id=doc_id,
            file_name=file_name,
            file_size_bytes=file_size,
            classification=ingest_res.classification.value,
            is_supported=True,
            page_count=ingest_res.page_count,
            ocr_used=ocr_res.ocr_used,
            ocr_confidence=ocr_res.average_ocr_confidence,
            quality_status=quality_status,
            quality_issues=quality_issues,
            technical_status=tech_status,
            facts_extracted_count=total_facts,
            message="Document processed successfully.",
        )

    def process_batch(
        self,
        files: List[Tuple[str, bytes]],
        patient_id: str = "SYN-CANCER-001",
    ) -> BatchProcessingReport:
        """Process multiple files independently and regenerate downstream artifacts."""
        start_time = time.time()
        if not files:
            return BatchProcessingReport(
                patient_id=patient_id,
                summary=BatchUploadSummary(
                    documents_received=0,
                    successfully_processed=0,
                    warnings=0,
                    failed=0,
                    processing_time_seconds=0.0,
                ),
                documents=[],
                artifacts_regenerated=False,
                message="No files provided for batch processing.",
                processing_time_seconds=0.0,
            )

        results: List[SingleDocumentResult] = []
        success_count = 0
        warning_count = 0
        failed_count = 0

        for fname, content in files:
            try:
                res = self.process_file_content(fname, content, patient_id=patient_id)
                results.append(res)
                if res.technical_status == "success":
                    success_count += 1
                elif res.technical_status == "needs_review":
                    warning_count += 1
                    # Document was still processed despite warning
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as exc:
                logger.error("Failed processing file %s: %s", fname, exc)
                failed_count += 1
                results.append(
                    SingleDocumentResult(
                        document_id="error",
                        file_name=fname,
                        file_size_bytes=len(content),
                        classification=DocumentClassification.UNSUPPORTED.value,
                        is_supported=False,
                        page_count=0,
                        ocr_used=False,
                        quality_status=QualityStatus.UNREADABLE.value,
                        quality_issues=[f"Internal processing error: {str(exc)}"],
                        technical_status="failed",
                        facts_extracted_count=0,
                        message="Failed to process document.",
                    )
                )

        # 8. Deterministic Downstream Artifact Regeneration
        regenerated = False
        if success_count > 0:
            try:
                self.regenerate_artifacts(patient_id=patient_id)
                regenerated = True
            except Exception as exc:
                logger.error("Failed downstream artifact regeneration: %s", exc)

        duration = round(time.time() - start_time, 2)
        summary = BatchUploadSummary(
            documents_received=len(files),
            successfully_processed=success_count,
            warnings=warning_count,
            failed=failed_count,
            processing_time_seconds=duration,
        )

        return BatchProcessingReport(
            patient_id=patient_id,
            summary=summary,
            documents=results,
            artifacts_regenerated=regenerated,
            message=(
                f"Batch processing completed: {success_count} succeeded, "
                f"{warning_count} with technical warnings, {failed_count} failed."
            ),
            processing_time_seconds=duration,
        )

    def regenerate_artifacts(self, patient_id: str = "SYN-CANCER-001") -> None:
        """Regenerate Timeline, Changes, Flags, and JourneyBrief from structured facts."""
        # 1. Timeline
        timeline_engine = TimelineEngine(self.structured_dir)
        timeline_engine.save_timeline(output_dir=self.timeline_dir, patient_id=patient_id)

        # 2. Changes
        change_detector = ChangeDetector(self.structured_dir)
        change_detector.save_changes(output_dir=self.changes_dir, patient_id=patient_id)

        # 3. Flags
        flag_detector = FlagDetector(self.structured_dir)
        flag_detector.save_flags(output_dir=self.flags_dir, patient_id=patient_id)

        # 4. JourneyBrief
        brief_gen = JourneyBriefGenerator(self.structured_dir, self.documents_dir)
        brief_gen.save_brief(output_dir=self.brief_dir, patient_id=patient_id)

    def reset_demo_baseline(self, patient_id: str = "SYN-CANCER-001") -> None:
        """Reset demo environment to the original 10-document synthetic baseline."""
        baseline_docs = {
            "doc-001_visit_note_2026-01-05.pdf",
            "doc-002_pathology_report_2026-01-08.pdf",
            "doc-003_laboratory_report_2026-01-10.pdf",
            "doc-004_imaging_report_2026-01-14.pdf",
            "doc-005_prescription_2026-01-15.pdf",
            "doc-006_procedure_note_2026-01-20.pdf",
            "doc-007_referral_letter_2026-01-21.pdf",
            "doc-008_laboratory_report_2026-02-05.pdf",
            "doc-009_followup_visit_2026-02-07.pdf",
            "doc-010_discharge_summary_2026-02-10.pdf",
            ".gitkeep",
        }
        baseline_structured = {
            "doc-001.json",
            "doc-002.json",
            "doc-003.json",
            "doc-004.json",
            "doc-005.json",
            "doc-006.json",
            "doc-007.json",
            "doc-008.json",
            "doc-009.json",
            "doc-010.json",
            "doc-003-gemini.json",
            ".gitkeep",
        }

        # 1. Remove non-baseline documents
        if self.documents_dir.exists():
            for p in self.documents_dir.glob("*"):
                if p.name not in baseline_docs:
                    try:
                        p.unlink()
                    except OSError:
                        pass

        # 2. Remove non-baseline structured facts
        if self.structured_dir.exists():
            for p in self.structured_dir.glob("*"):
                if p.name not in baseline_structured:
                    try:
                        p.unlink()
                    except OSError:
                        pass

        # 3. Clean uploaded messy docs if any
        if self.uploads_dir.exists():
            for p in self.uploads_dir.glob("*"):
                if p.name != ".gitkeep":
                    try:
                        p.unlink()
                    except OSError:
                        pass

        # 4. Reset review state to pending baseline
        sanitized = patient_id.lower().replace("-", "_")
        for rf in [
            Path("data/reviews") / f"{patient_id}.json",
            Path("data/reviews") / f"{sanitized}_review.json",
        ]:
            if rf.exists():
                try:
                    rf.unlink()
                except OSError:
                    pass

        # 5. Deterministically regenerate downstream artifacts from baseline
        self.regenerate_artifacts(patient_id=patient_id)
