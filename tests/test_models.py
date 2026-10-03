import unittest
from datetime import date
from pydantic import ValidationError

from app.models.source import SourceReference
from app.models.document import Document, DocumentType
from app.models.patient import Patient
from app.models.clinical import (
    Visit,
    PathologyFinding,
    LaboratoryResult,
    ImagingReport,
    MedicationRecord,
    ProcedureRecord,
    ReferralRecord,
    InvestigationRecord,
    TimelineEvent,
    PatientJourney,
)


class TestCancerCareDataModels(unittest.TestCase):
    """Test suite for Cancer Care structured data models and safety constraints."""

    def setUp(self) -> None:
        self.sample_source = SourceReference(
            document_id="DOC-SYNTH-001",
            file_name="histopathology_biopsy.pdf",
            page_number=1,
            text_anchor="Invasive ductal carcinoma, Nottingham grade 2",
            bounding_box=[72.0, 144.0, 400.0, 200.0],
        )

    def test_valid_patient_journey_creation(self) -> None:
        """1. Verify valid PatientJourney creation with all clinical domain models."""
        document = Document(
            document_id="DOC-SYNTH-001",
            file_name="histopathology_biopsy.pdf",
            document_type=DocumentType.PATHOLOGY_REPORT,
            document_date=date(2024, 3, 15),
            page_count=3,
        )

        patient = Patient(
            patient_id="SYNTH-PT-001",
            synthetic=True,
            documents=[document],
        )

        visit = Visit(
            visit_id="VIS-001",
            date=date(2024, 3, 10),
            facility="St. Jude Synthetic Cancer Center",
            department="Surgical Oncology",
            visit_type="Initial Consultation",
            source=self.sample_source,
            confidence=0.98,
        )

        pathology = PathologyFinding(
            finding_name="Core Needle Biopsy, Right Breast",
            documented_text="Invasive ductal carcinoma, histological grade 2, ER positive 80%, PR positive 60%, HER2 negative (1+ by IHC).",
            date=date(2024, 3, 15),
            source=self.sample_source,
            confidence=0.95,
        )

        lab = LaboratoryResult(
            test_name="CA 15-3",
            value="24.5",
            unit="U/mL",
            reference_range_text="0.0 - 30.0 U/mL",
            date=date(2024, 3, 12),
            source=self.sample_source,
            confidence=0.99,
        )

        imaging = ImagingReport(
            modality="Contrast-Enhanced CT Chest/Abdomen/Pelvis",
            body_site="Chest, Abdomen, Pelvis",
            report_text="No evidence of distant metastatic disease. 2.1 cm enhancing mass in upper outer quadrant of right breast.",
            date=date(2024, 3, 14),
            source=self.sample_source,
            confidence=0.94,
        )

        medication = MedicationRecord(
            medicine_name="Tamoxifen",
            strength="20 mg",
            dose="20 mg once daily",
            frequency="Daily",
            route="Oral",
            status="started",
            date=date(2024, 3, 20),
            source=self.sample_source,
            confidence=0.92,
        )

        procedure = ProcedureRecord(
            procedure_name="Ultrasound-guided core needle biopsy of right breast mass",
            date=date(2024, 3, 14),
            documented_status="completed",
            source=self.sample_source,
            confidence=0.96,
        )

        referral = ReferralRecord(
            referred_to="Medical Oncology",
            date=date(2024, 3, 16),
            status="scheduled",
            source=self.sample_source,
            confidence=0.91,
        )

        investigation = InvestigationRecord(
            investigation_name="Cardiac Echocardiogram (pre-chemotherapy assessment)",
            status="completed",
            ordered_date=date(2024, 3, 16),
            result_date=date(2024, 3, 18),
            source=self.sample_source,
            confidence=0.93,
        )

        timeline_event = TimelineEvent(
            event_id="EVT-001",
            date=date(2024, 3, 14),
            event_type="Procedure",
            description="Documented right breast ultrasound-guided biopsy performed.",
            source=self.sample_source,
            confidence=0.96,
        )

        journey = PatientJourney(
            patient=patient,
            visits=[visit],
            pathology_findings=[pathology],
            laboratory_results=[lab],
            imaging_reports=[imaging],
            medications=[medication],
            procedures=[procedure],
            referrals=[referral],
            investigations=[investigation],
            timeline_events=[timeline_event],
        )

        self.assertEqual(journey.patient.patient_id, "SYNTH-PT-001")
        self.assertTrue(journey.patient.synthetic)
        self.assertEqual(len(journey.visits), 1)
        self.assertEqual(len(journey.pathology_findings), 1)
        self.assertEqual(len(journey.laboratory_results), 1)
        self.assertEqual(len(journey.imaging_reports), 1)
        self.assertEqual(len(journey.medications), 1)
        self.assertEqual(len(journey.procedures), 1)
        self.assertEqual(len(journey.referrals), 1)
        self.assertEqual(len(journey.investigations), 1)
        self.assertEqual(len(journey.timeline_events), 1)

    def test_invalid_confidence_rejected(self) -> None:
        """2. Verify that confidence values outside [0.0, 1.0] are rejected."""
        # Value > 1.0
        with self.assertRaises(ValidationError):
            Visit(
                visit_id="VIS-001",
                date=date(2024, 3, 10),
                source=self.sample_source,
                confidence=1.05,
            )

        # Value < 0.0
        with self.assertRaises(ValidationError):
            Visit(
                visit_id="VIS-001",
                date=date(2024, 3, 10),
                source=self.sample_source,
                confidence=-0.1,
            )

        # Non-numeric value
        with self.assertRaises(ValidationError):
            Visit(
                visit_id="VIS-001",
                date=date(2024, 3, 10),
                source=self.sample_source,
                confidence="high",  # type: ignore
            )

    def test_invalid_page_number_rejected(self) -> None:
        """3. Verify that page numbers < 1 are rejected."""
        # page_number = 0
        with self.assertRaises(ValidationError):
            SourceReference(
                document_id="DOC-001",
                file_name="report.pdf",
                page_number=0,
            )

        # Negative page_number
        with self.assertRaises(ValidationError):
            SourceReference(
                document_id="DOC-001",
                file_name="report.pdf",
                page_number=-3,
            )

    def test_missing_source_rejected(self) -> None:
        """4. Verify that clinical records require a valid SourceReference."""
        # Missing source in Visit
        with self.assertRaises(ValidationError):
            Visit(
                visit_id="VIS-001",
                date=date(2024, 3, 10),
                confidence=0.95,
            )  # type: ignore[call-arg]

        # Missing source in PathologyFinding
        with self.assertRaises(ValidationError):
            PathologyFinding(
                finding_name="Biopsy",
                documented_text="Carcinoma in situ",
                confidence=0.90,
            )  # type: ignore[call-arg]

        # Missing source in LaboratoryResult
        with self.assertRaises(ValidationError):
            LaboratoryResult(
                test_name="Hemoglobin",
                value="13.2",
                confidence=0.95,
            )  # type: ignore[call-arg]

        # Missing source in ImagingReport
        with self.assertRaises(ValidationError):
            ImagingReport(
                modality="MRI",
                report_text="No acute finding",
                confidence=0.90,
            )  # type: ignore[call-arg]

    def test_patient_defaults_to_synthetic_true(self) -> None:
        """5. Verify that Patient model strictly defaults synthetic to True."""
        patient = Patient(patient_id="SYNTH-999")
        self.assertTrue(patient.synthetic)

    def test_invalid_date_rejected(self) -> None:
        """6. Verify that invalid ISO dates or non-dates are rejected by Pydantic."""
        # Out-of-bounds calendar date (e.g. Feb 30)
        with self.assertRaises(ValidationError):
            Visit(
                visit_id="VIS-001",
                date="2024-02-30",  # type: ignore[arg-type]
                source=self.sample_source,
                confidence=0.95,
            )

        # Invalid date format string
        with self.assertRaises(ValidationError):
            Visit(
                visit_id="VIS-001",
                date="not-a-valid-date",  # type: ignore[arg-type]
                source=self.sample_source,
                confidence=0.95,
            )

        # Invalid month
        with self.assertRaises(ValidationError):
            Document(
                document_id="DOC-001",
                file_name="note.pdf",
                document_type=DocumentType.VISIT_NOTE,
                document_date="2024-13-01",  # type: ignore[arg-type]
            )

    def test_imaging_report_prohibited_clinical_fields(self) -> None:
        """7. Verify ImagingReport forbids clinical interpretation / inferred fields."""
        prohibited_fields = {
            "tumor_size_change",
            "progression",
            "response",
            "severity",
            "stage",
            "prognosis",
            "clinical_interpretation",
        }

        # Verify no prohibited field exists on the model definition
        model_field_names = set(ImagingReport.model_fields.keys())
        intersection = model_field_names.intersection(prohibited_fields)
        self.assertEqual(
            intersection,
            set(),
            f"ImagingReport contains prohibited clinical interpretation fields: {intersection}",
        )

        # Verify extra="forbid" rejects any prohibited field passed dynamically
        with self.assertRaises(ValidationError):
            ImagingReport(
                modality="CT Chest",
                report_text="Stable appearance",
                source=self.sample_source,
                confidence=0.95,
                tumor_size_change="increased",  # type: ignore[call-arg]
            )

        with self.assertRaises(ValidationError):
            ImagingReport(
                modality="PET-CT",
                report_text="Metabolically active lesions",
                source=self.sample_source,
                confidence=0.95,
                progression="disease progression",  # type: ignore[call-arg]
            )


if __name__ == "__main__":
    unittest.main()
