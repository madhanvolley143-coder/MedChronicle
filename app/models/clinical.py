from datetime import date as dt_date
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.patient import Patient
from app.models.source import SourceReference


class ClinicalFactBase(BaseModel):
    """Base class for all extracted clinical facts enforcing source traceability and confidence."""

    model_config = ConfigDict(extra="forbid")

    source: SourceReference = Field(
        ...,
        description="Mandatory source document reference with page number provenance",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Fact extraction confidence score strictly bounded between 0.0 and 1.0",
    )


class Visit(ClinicalFactBase):
    """Documented clinical encounter or consultation."""

    visit_id: str = Field(..., min_length=1, description="Unique identifier for the encounter")
    date: dt_date = Field(..., description="Documented date of encounter in ISO format")
    facility: Optional[str] = Field(default=None, description="Documented healthcare facility name")
    department: Optional[str] = Field(default=None, description="Documented clinic or department")
    visit_type: Optional[str] = Field(default=None, description="Documented visit type (e.g. outpatient, oncology consult)")


class PathologyFinding(ClinicalFactBase):
    """Documented pathology finding.

    STRICT SAFETY BOUNDARY:
    Represents documented text only. No AI stage inference, grading, or clinical interpretation.
    """

    finding_name: str = Field(..., min_length=1, description="Documented finding title or specimen name")
    documented_text: str = Field(..., min_length=1, description="Exact documented findings text from report")
    date: Optional[dt_date] = Field(default=None, description="Specimen or report date in ISO format")


class LaboratoryResult(ClinicalFactBase):
    """Documented laboratory test result.

    STRICT SAFETY BOUNDARY:
    Reference range is stored as text only. Never classify the result as normal/abnormal.
    """

    test_name: str = Field(..., min_length=1, description="Documented laboratory test or panel name")
    value: str = Field(..., min_length=1, description="Documented test value as recorded in document")
    unit: Optional[str] = Field(default=None, description="Measurement unit as documented")
    reference_range_text: Optional[str] = Field(
        default=None,
        description="Reference interval text as documented. No normal/abnormal classification.",
    )
    date: Optional[dt_date] = Field(default=None, description="Collection or result date in ISO format")


class ImagingReport(ClinicalFactBase):
    """Documented imaging report.

    STRICT SAFETY BOUNDARY:
    Contains documented report text only. Prohibited fields:
    tumor_size_change, progression, response, severity, or stage assessment.
    """

    modality: str = Field(..., min_length=1, description="Documented modality (e.g. CT, MRI, PET-CT, Mammogram)")
    body_site: Optional[str] = Field(default=None, description="Anatomical site investigated")
    report_text: str = Field(..., min_length=1, description="Documented radiological impression and report text")
    date: Optional[dt_date] = Field(default=None, description="Date of study in ISO format")


class MedicationRecord(ClinicalFactBase):
    """Documented medication entry.

    STRICT SAFETY BOUNDARY:
    Status represents documented status only (e.g., listed, started, stopped, continued, unknown).
    No inferred rationale for medication changes.
    """

    medicine_name: str = Field(..., min_length=1, description="Documented medication brand or generic name")
    strength: Optional[str] = Field(default=None, description="Documented drug strength (e.g. 50 mg)")
    dose: Optional[str] = Field(default=None, description="Documented dosage instructions")
    frequency: Optional[str] = Field(default=None, description="Documented dosage frequency")
    route: Optional[str] = Field(default=None, description="Documented administration route")
    status: Optional[str] = Field(
        default=None,
        description="Documented status: listed, started, stopped, continued, unknown",
    )
    date: Optional[dt_date] = Field(default=None, description="Documented prescription or administration date")


class ProcedureRecord(ClinicalFactBase):
    """Documented surgical or diagnostic procedure."""

    procedure_name: str = Field(..., min_length=1, description="Documented procedure or surgical intervention name")
    date: Optional[dt_date] = Field(default=None, description="Documented procedure date in ISO format")
    documented_status: Optional[str] = Field(default=None, description="Status documented in notes (e.g. performed, planned)")


class ReferralRecord(ClinicalFactBase):
    """Documented patient referral."""

    referred_to: str = Field(..., min_length=1, description="Documented receiving physician, specialty, or department")
    date: Optional[dt_date] = Field(default=None, description="Referral request date in ISO format")
    status: Optional[str] = Field(default=None, description="Referral status documented in records")


class InvestigationRecord(ClinicalFactBase):
    """Documented diagnostic investigation order or tracking."""

    investigation_name: str = Field(..., min_length=1, description="Documented diagnostic investigation name")
    status: str = Field(
        ...,
        min_length=1,
        description="Investigation status: ordered, completed, result_available, result_not_found, unknown",
    )
    ordered_date: Optional[dt_date] = Field(default=None, description="Order date in ISO format")
    result_date: Optional[dt_date] = Field(default=None, description="Result availability date in ISO format")


class TimelineEvent(ClinicalFactBase):
    """Chronological patient timeline event.

    STRICT SAFETY BOUNDARY:
    Description must represent documented information only without AI extrapolation.
    """

    event_id: str = Field(..., min_length=1, description="Unique identifier for timeline event")
    date: dt_date = Field(..., description="Chronological event date in ISO format")
    event_type: str = Field(..., min_length=1, description="Documented event category (e.g. biopsy, surgery, imaging)")
    description: str = Field(..., min_length=1, description="Factual description derived directly from records")


class PatientJourney(BaseModel):
    """Top-level patient journey representation composed entirely of documented facts."""

    model_config = ConfigDict(extra="forbid")

    patient: Patient = Field(..., description="Synthetic patient demographic and document profile")
    visits: List[Visit] = Field(default_factory=list, description="Documented patient visits")
    pathology_findings: List[PathologyFinding] = Field(default_factory=list, description="Documented pathology findings")
    laboratory_results: List[LaboratoryResult] = Field(default_factory=list, description="Documented laboratory tests")
    imaging_reports: List[ImagingReport] = Field(default_factory=list, description="Documented imaging studies")
    medications: List[MedicationRecord] = Field(default_factory=list, description="Documented medications")
    procedures: List[ProcedureRecord] = Field(default_factory=list, description="Documented procedures")
    referrals: List[ReferralRecord] = Field(default_factory=list, description="Documented referrals")
    investigations: List[InvestigationRecord] = Field(default_factory=list, description="Documented investigations")
    timeline_events: List[TimelineEvent] = Field(default_factory=list, description="Chronological documented events")
