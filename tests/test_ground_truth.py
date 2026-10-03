import json
import unittest
from pathlib import Path

from app.models import PatientJourney, SourceReference


class TestGroundTruthDataset(unittest.TestCase):
    """Test suite verifying the synthetic Cancer Care ground-truth dataset."""

    GROUND_TRUTH_PATH = Path("data/ground_truth/patient_001.json")

    @classmethod
    def setUpClass(cls) -> None:
        if cls.GROUND_TRUTH_PATH.is_file():
            cls.raw_data = json.loads(cls.GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
            cls.journey = PatientJourney.model_validate(cls.raw_data)
        else:
            cls.raw_data = None
            cls.journey = None

    def _get_all_facts(self):
        """Helper to collect all clinical facts and timeline events."""
        self.assertIsNotNone(self.journey, "Journey data failed to load")
        facts = []
        facts.extend(self.journey.visits)
        facts.extend(self.journey.pathology_findings)
        facts.extend(self.journey.laboratory_results)
        facts.extend(self.journey.imaging_reports)
        facts.extend(self.journey.medications)
        facts.extend(self.journey.procedures)
        facts.extend(self.journey.referrals)
        facts.extend(self.journey.investigations)
        facts.extend(self.journey.timeline_events)
        return facts

    def test_01_patient_json_exists(self) -> None:
        """1. Verify patient_001.json exists at data/ground_truth/patient_001.json."""
        self.assertTrue(
            self.GROUND_TRUTH_PATH.is_file(),
            f"Expected ground truth file not found at {self.GROUND_TRUTH_PATH}",
        )

    def test_02_json_loads_successfully(self) -> None:
        """2. Verify JSON loads successfully from file."""
        self.assertIsInstance(self.raw_data, dict)
        self.assertIn("patient", self.raw_data)

    def test_03_validates_with_patient_journey(self) -> None:
        """3. Verify JSON parses and validates cleanly into PatientJourney model."""
        self.assertIsInstance(self.journey, PatientJourney)
        self.assertEqual(self.journey.patient.patient_id, "SYN-CANCER-001")

    def test_04_patient_synthetic_is_true(self) -> None:
        """4. Verify patient.synthetic is explicitly True."""
        self.assertTrue(self.journey.patient.synthetic)

    def test_05_at_least_eight_documents(self) -> None:
        """5. Verify there are at least 8 synthetic documents defined."""
        doc_count = len(self.journey.patient.documents)
        self.assertGreaterEqual(
            doc_count,
            8,
            f"Expected at least 8 documents, but found {doc_count}",
        )

    def test_06_every_clinical_fact_has_source(self) -> None:
        """6. Verify every clinical fact and event has a non-null SourceReference."""
        facts = self._get_all_facts()
        self.assertGreater(len(facts), 0, "No clinical facts found in journey")
        for fact in facts:
            self.assertTrue(hasattr(fact, "source"), f"{type(fact).__name__} lacks a source attribute")
            self.assertIsInstance(
                fact.source,
                SourceReference,
                f"{type(fact).__name__} source is not a SourceReference",
            )
            self.assertTrue(fact.source.document_id)
            self.assertTrue(fact.source.file_name)

    def test_07_every_source_doc_id_exists_in_patient_documents(self) -> None:
        """7. Verify every source document_id corresponds to a document in Patient.documents."""
        doc_map = {doc.document_id: doc.file_name for doc in self.journey.patient.documents}
        facts = self._get_all_facts()
        for fact in facts:
            doc_id = fact.source.document_id
            self.assertIn(
                doc_id,
                doc_map,
                f"Source document_id '{doc_id}' not found in patient.documents",
            )
            self.assertEqual(
                fact.source.file_name,
                doc_map[doc_id],
                f"Source file_name '{fact.source.file_name}' does not match document record '{doc_map[doc_id]}'",
            )

    def test_08_every_source_page_number_ge_one(self) -> None:
        """8. Verify every source page_number is greater than or equal to 1."""
        facts = self._get_all_facts()
        for fact in facts:
            self.assertGreaterEqual(
                fact.source.page_number,
                1,
                f"Invalid page_number {fact.source.page_number} in {type(fact).__name__}",
            )

    def test_09_every_confidence_between_zero_and_one(self) -> None:
        """9. Verify every confidence score is bounded between 0.0 and 1.0."""
        facts = self._get_all_facts()
        for fact in facts:
            self.assertGreaterEqual(fact.confidence, 0.0)
            self.assertLessEqual(fact.confidence, 1.0)

    def test_10_no_prohibited_clinical_interpretation_fields(self) -> None:
        """10. Verify prohibited clinical interpretation fields and phrases are absent."""
        prohibited_field_names = {
            "tumor_size_change",
            "progression",
            "response",
            "severity",
            "stage",
            "prognosis",
            "clinical_interpretation",
            "treatment_recommendation",
            "risk_score",
        }

        facts = self._get_all_facts()
        for fact in facts:
            fact_fields = set(type(fact).model_fields.keys())
            overlap = fact_fields.intersection(prohibited_field_names)
            self.assertEqual(
                overlap,
                set(),
                f"Fact {type(fact).__name__} contains prohibited fields: {overlap}",
            )

        # Verify no prohibited extrapolation phrases in any text field
        prohibited_phrases = [
            "cancer is progressing",
            "treatment is working",
            "poor response",
            "advanced stage",
            "severe disease",
            "high risk",
        ]
        raw_json_str = json.dumps(self.raw_data).lower()
        for phrase in prohibited_phrases:
            self.assertNotIn(
                phrase,
                raw_json_str,
                f"Found prohibited clinical conclusion phrase '{phrase}' in ground truth JSON",
            )


if __name__ == "__main__":
    unittest.main()
