"""Unit tests for JourneyBrief extraction evaluation service.

Verifies:
1. Ground truth loads cleanly.
2. Structured output files load properly.
3. Document coverage calculation.
4. Fact matching logic across categories.
5. Detection of missing clinical facts.
6. Provenance validation (source document ID, file, page).
7. Safety prohibited clinical fields / concepts detection.
8. Confidence statistics computation.
9. Report serialization to JSON and Markdown.
10. Handling of missing / failed documents.

None of these tests call Ollama or external services.
"""

import json
from pathlib import Path
import tempfile
import unittest

from app.services.evaluation import (
    EvaluationService,
    PROHIBITED_SAFETY_KEYS,
)


class TestExtractionEvaluation(unittest.TestCase):
    """Test suite for evaluation service metrics, provenance, safety, and reporting."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name)
        self.ground_truth_path = self.root_path / "ground_truth.json"
        self.structured_dir = self.root_path / "structured"
        self.structured_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = self.root_path / "evaluation"

        # Create minimal synthetic ground truth
        self.sample_gt = {
            "patient": {"patient_id": "SYN-CANCER-001", "synthetic": True},
            "visits": [
                {
                    "source": {
                        "document_id": "doc-001",
                        "file_name": "visit_note_2026-01-05.pdf",
                        "page_number": 1,
                    },
                    "confidence": 0.98,
                    "visit_id": "VIS-001",
                    "date": "2026-01-05",
                    "facility": "Sunrise Oncology Centre",
                    "department": "Surgical Oncology",
                }
            ],
            "laboratory_results": [
                {
                    "source": {
                        "document_id": "doc-003",
                        "file_name": "laboratory_report_2026-01-10.pdf",
                        "page_number": 1,
                    },
                    "confidence": 0.98,
                    "test_name": "CA 15-3",
                    "value": "22.4",
                    "unit": "U/mL",
                    "date": "2026-01-10",
                },
                {
                    "source": {
                        "document_id": "doc-003",
                        "file_name": "laboratory_report_2026-01-10.pdf",
                        "page_number": 1,
                    },
                    "confidence": 0.99,
                    "test_name": "Hemoglobin",
                    "value": "13.4",
                    "unit": "g/dL",
                    "date": "2026-01-10",
                },
            ],
            "medications": [
                {
                    "source": {
                        "document_id": "doc-005",
                        "file_name": "prescription_2026-01-15.pdf",
                        "page_number": 1,
                    },
                    "confidence": 0.95,
                    "medicine_name": "Tamoxifen",
                    "strength": "20 mg",
                    "status": "started",
                    "date": "2026-01-15",
                }
            ],
        }
        self.ground_truth_path.write_text(json.dumps(self.sample_gt), encoding="utf-8")

        # Create matching sample structured outputs
        doc_001_data = {
            "document_id": "doc-001",
            "file_name": "doc-001_visit_note_2026-01-05.pdf",
            "pages_processed": 1,
            "facts": {
                "visits": [
                    {
                        "source": {
                            "document_id": "doc-001",
                            "file_name": "doc-001_visit_note_2026-01-05.pdf",
                            "page_number": 1,
                        },
                        "confidence": 1.0,
                        "date": "2026-01-05",
                        "facility": "Sunrise Oncology Centre",
                        "department": "Surgical Oncology",
                    }
                ]
            },
        }
        (self.structured_dir / "doc-001.json").write_text(json.dumps(doc_001_data), encoding="utf-8")

        doc_003_data = {
            "document_id": "doc-003",
            "file_name": "doc-003_laboratory_report_2026-01-10.pdf",
            "pages_processed": 1,
            "facts": {
                "laboratory_results": [
                    {
                        "source": {
                            "document_id": "doc-003",
                            "file_name": "doc-003_laboratory_report_2026-01-10.pdf",
                            "page_number": 1,
                        },
                        "confidence": 1.0,
                        "test_name": "CA 15-3",
                        "value": "22.4",
                        "unit": "U/mL",
                        "date": "2026-01-10",
                    }
                ]
            },
        }
        (self.structured_dir / "doc-003.json").write_text(json.dumps(doc_003_data), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_01_evaluation_loads_ground_truth(self) -> None:
        """1. Verify evaluation service loads ground truth successfully."""
        service = EvaluationService(self.ground_truth_path, self.structured_dir)
        gt = service.load_ground_truth()
        self.assertEqual(gt["patient"]["patient_id"], "SYN-CANCER-001")
        self.assertIn("laboratory_results", gt)

    def test_02_evaluation_loads_structured_output(self) -> None:
        """2. Verify evaluation service loads structured files from directory."""
        service = EvaluationService(self.ground_truth_path, self.structured_dir)
        docs = service.load_structured_documents()
        self.assertIn("doc-001", docs)
        self.assertIn("doc-003", docs)
        self.assertEqual(len(docs), 2)

    def test_03_document_coverage_calculation(self) -> None:
        """3. Verify document coverage percentage and missing documents list."""
        expected = ["doc-001", "doc-002", "doc-003", "doc-004"]
        service = EvaluationService(self.ground_truth_path, self.structured_dir, expected_documents=expected)
        metrics = service.evaluate()
        cov = metrics["document_coverage"]
        self.assertEqual(cov["expected_count"], 4)
        self.assertEqual(cov["successful_count"], 2)
        self.assertEqual(cov["failed_count"], 2)
        self.assertEqual(cov["coverage_pct"], 50.0)
        self.assertEqual(cov["failed_documents"], ["doc-002", "doc-004"])

    def test_04_fact_matching_works(self) -> None:
        """4. Verify fact matching for correctly extracted entities."""
        service = EvaluationService(self.ground_truth_path, self.structured_dir)
        metrics = service.evaluate()
        lab_metrics = metrics["fact_metrics"]["laboratory_results"]
        # In ground truth there are 2 labs (CA 15-3 and Hemoglobin). In structured, only CA 15-3 was provided.
        self.assertEqual(lab_metrics["matched"], 1)
        self.assertEqual(lab_metrics["missing"], 1)

    def test_05_missing_facts_are_detected(self) -> None:
        """5. Verify unextracted ground truth facts are tallied as missing."""
        service = EvaluationService(self.ground_truth_path, self.structured_dir)
        metrics = service.evaluate()
        med_metrics = metrics["fact_metrics"]["medications"]
        # Ground truth has Tamoxifen in doc-005, but doc-005 was not loaded.
        self.assertEqual(med_metrics["expected"], 1)
        self.assertEqual(med_metrics["matched"], 0)
        self.assertEqual(med_metrics["missing"], 1)

    def test_06_provenance_validation_works(self) -> None:
        """6. Verify provenance validation detects invalid or missing source provenance."""
        # Insert a document with corrupted provenance
        bad_doc = {
            "document_id": "doc-099",
            "file_name": "bad.pdf",
            "facts": {
                "laboratory_results": [
                    {
                        "source": {
                            "document_id": "WRONG_ID",
                            "file_name": "bad_file.txt",  # Not .pdf
                            "page_number": 0,             # Page < 1
                        },
                        "confidence": 0.9,
                        "test_name": "Test",
                        "value": "1",
                    }
                ]
            },
        }
        (self.structured_dir / "doc-099.json").write_text(json.dumps(bad_doc), encoding="utf-8")

        service = EvaluationService(self.ground_truth_path, self.structured_dir)
        docs = service.load_structured_documents()
        prov_results = service.verify_provenance(docs)

        self.assertFalse(prov_results["passed"])
        self.assertGreater(prov_results["issues_count"], 0)

    def test_07_safety_prohibited_field_detection(self) -> None:
        """7. Verify safety check fails if prohibited clinical inference fields appear."""
        unsafe_doc = {
            "document_id": "doc-002",
            "file_name": "doc-002_pathology.pdf",
            "facts": {
                "pathology_findings": [
                    {
                        "finding_name": "Core Biopsy",
                        "cancer_stage": "Stage IIA",  # PROHIBITED FIELD
                        "confidence": 0.9,
                    }
                ]
            },
        }
        (self.structured_dir / "doc-002.json").write_text(json.dumps(unsafe_doc), encoding="utf-8")

        service = EvaluationService(self.ground_truth_path, self.structured_dir)
        docs = service.load_structured_documents()
        safety_results = service.verify_safety(docs)

        self.assertFalse(safety_results["passed"])
        self.assertGreater(safety_results["violations_count"], 0)
        violation_types = [v["violation_type"] for v in safety_results["violations"]]
        self.assertIn("prohibited_key", violation_types)

    def test_08_confidence_statistics_calculation(self) -> None:
        """8. Verify confidence calculation correctly tallies min, max, avg, and 1.0 counts."""
        service = EvaluationService(self.ground_truth_path, self.structured_dir)
        docs = service.load_structured_documents()
        stats = service.calculate_confidence_stats(docs)

        self.assertEqual(stats["total_facts"], 2)
        self.assertEqual(stats["min_confidence"], 1.0)
        self.assertEqual(stats["max_confidence"], 1.0)
        self.assertEqual(stats["average_confidence"], 1.0)
        self.assertEqual(stats["facts_at_1_0"], 2)
        self.assertEqual(stats["facts_at_1_0_pct"], 100.0)

    def test_09_evaluation_json_and_md_serializable(self) -> None:
        """9. Verify save_reports writes valid JSON and non-empty Markdown report."""
        service = EvaluationService(self.ground_truth_path, self.structured_dir)
        json_path, md_path = service.save_reports(self.output_dir, processing_time_seconds=12.5)

        self.assertTrue(json_path.is_file())
        self.assertTrue(md_path.is_file())

        saved_data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(saved_data["project"], "JourneyBrief")
        self.assertEqual(saved_data["domain"], "Cancer Care")
        self.assertEqual(saved_data["processing_time_seconds"], 12.5)

        md_text = md_path.read_text(encoding="utf-8")
        self.assertIn("JourneyBrief — Full Cancer Document Extraction & Ground Truth Evaluation Report", md_text)
        self.assertIn("1. Executive Summary", md_text)

    def test_10_evaluation_handles_missing_document(self) -> None:
        """10. Verify evaluation gracefully handles when an expected document is missing."""
        service = EvaluationService(
            self.ground_truth_path,
            self.structured_dir,
            expected_documents=["doc-001", "doc-010"],
        )
        metrics = service.evaluate()
        self.assertEqual(metrics["documents_failed"], 1)
        self.assertIn("doc-010", metrics["document_coverage"]["failed_documents"])


if __name__ == "__main__":
    unittest.main()
