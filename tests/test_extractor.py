import json
import os
import unittest
from pathlib import Path
from typing import Any, Dict

from app.services.extractor import (
    ExtractionParseError,
    ExtractionService,
    ExtractionValidationError,
    OllamaConnectionError,
)
from app.services.prompts import EXTRACTION_SYSTEM_PROMPT


class TestExtractionService(unittest.TestCase):
    """Test suite verifying controlled structured extraction, safety boundaries, and error handling."""

    EXTRACTED_DOC_PATH = Path("data/extracted/doc-001.json")

    def setUp(self) -> None:
        # Sample document data loaded from data/extracted/doc-001.json
        self.doc_data: Dict[str, Any] = {
            "document_id": "doc-001",
            "file_name": "doc-001_visit_note_2026-01-05.pdf",
            "page_count": 2,
            "pages": [
                {
                    "page_number": 1,
                    "text": "Initial oncology consultation for palpable right breast mass.",
                },
                {
                    "page_number": 2,
                    "text": "Diagnostic Mammogram and Breast Ultrasound ordered on 2026-01-05.",
                },
            ],
        }

    @staticmethod
    def mock_llm_valid_response(prompt: str, system_prompt: str) -> str:
        """Deterministic mock LLM response returning valid structured clinical facts."""
        if "Page Number: 1" in prompt:
            return json.dumps(
                {
                    "visits": [
                        {
                            "visit_id": "VIS-001",
                            "date": "2026-01-05",
                            "facility": "Sunrise Oncology Centre",
                            "department": "Surgical Oncology",
                            "visit_type": "Initial Consultation",
                            "text_anchor": "Initial oncology consultation for palpable right breast mass",
                            "confidence": 0.98,
                        }
                    ],
                    "timeline_events": [
                        {
                            "event_id": "EVT-001",
                            "date": "2026-01-05",
                            "event_type": "Visit",
                            "description": "Documented initial surgical oncology outpatient consultation.",
                            "confidence": 0.98,
                        }
                    ],
                }
            )
        else:
            return json.dumps(
                {
                    "investigations": [
                        {
                            "investigation_name": "Diagnostic Mammogram and Breast Ultrasound",
                            "status": "ordered",
                            "ordered_date": "2026-01-05",
                            "result_date": None,
                            "text_anchor": "Diagnostic Mammogram and Breast Ultrasound ordered on 2026-01-05",
                            "confidence": 0.95,
                        }
                    ]
                }
            )

    def test_01_extracted_document_json_loads(self) -> None:
        """1. Verify extracted document JSON loads from data/extracted/doc-001.json."""
        self.assertTrue(self.EXTRACTED_DOC_PATH.is_file(), f"Missing {self.EXTRACTED_DOC_PATH}")
        data = json.loads(self.EXTRACTED_DOC_PATH.read_text(encoding="utf-8"))
        self.assertEqual(data["document_id"], "doc-001")
        self.assertGreaterEqual(len(data["pages"]), 1)

    def test_02_output_schema_is_valid(self) -> None:
        """2. Verify output schema contains expected keys and fact collections."""
        service = ExtractionService(llm_client=self.mock_llm_valid_response)
        result = service.extract_document(self.doc_data)

        self.assertIn("document_id", result)
        self.assertIn("file_name", result)
        self.assertIn("pages_processed", result)
        self.assertIn("facts", result)

        expected_categories = [
            "visits",
            "pathology_findings",
            "laboratory_results",
            "imaging_reports",
            "medications",
            "procedures",
            "referrals",
            "investigations",
            "timeline_events",
        ]
        for cat in expected_categories:
            self.assertIn(cat, result["facts"])
            self.assertIsInstance(result["facts"][cat], list)

        self.assertEqual(len(result["facts"]["visits"]), 1)
        self.assertEqual(len(result["facts"]["investigations"]), 1)
        self.assertEqual(len(result["facts"]["timeline_events"]), 1)

    def test_03_source_document_id_is_preserved(self) -> None:
        """3. Verify source document_id is injected and preserved in all extracted facts."""
        service = ExtractionService(llm_client=self.mock_llm_valid_response)
        result = service.extract_document(self.doc_data)

        visit_fact = result["facts"]["visits"][0]
        self.assertEqual(visit_fact["source"]["document_id"], "doc-001")

        inv_fact = result["facts"]["investigations"][0]
        self.assertEqual(inv_fact["source"]["document_id"], "doc-001")

    def test_04_source_file_name_is_preserved(self) -> None:
        """4. Verify source file_name is injected and preserved in all extracted facts."""
        service = ExtractionService(llm_client=self.mock_llm_valid_response)
        result = service.extract_document(self.doc_data)

        visit_fact = result["facts"]["visits"][0]
        self.assertEqual(visit_fact["source"]["file_name"], "doc-001_visit_note_2026-01-05.pdf")

    def test_05_source_page_number_is_preserved(self) -> None:
        """5. Verify source page_number reflects the exact page where the fact was found."""
        service = ExtractionService(llm_client=self.mock_llm_valid_response)
        result = service.extract_document(self.doc_data)

        # Visit was on page 1
        visit_fact = result["facts"]["visits"][0]
        self.assertEqual(visit_fact["source"]["page_number"], 1)

        # Investigation was on page 2
        inv_fact = result["facts"]["investigations"][0]
        self.assertEqual(inv_fact["source"]["page_number"], 2)

    def test_06_invalid_confidence_is_rejected(self) -> None:
        """6. Verify confidence values < 0.0 or > 1.0 raise ExtractionValidationError."""
        def mock_invalid_confidence(prompt: str, system_prompt: str) -> str:
            return json.dumps(
                {
                    "visits": [
                        {
                            "visit_id": "VIS-001",
                            "date": "2026-01-05",
                            "confidence": 1.5,  # Invalid: > 1.0
                        }
                    ]
                }
            )

        service = ExtractionService(llm_client=mock_invalid_confidence)
        with self.assertRaises(ExtractionValidationError):
            service.extract_page("doc-001", "file.pdf", 1, "Some clinical text")

    def test_07_unknown_fields_are_rejected(self) -> None:
        """7. Verify unknown / non-schema fields are rejected by Pydantic extra='forbid'."""
        def mock_unknown_fields(prompt: str, system_prompt: str) -> str:
            return json.dumps(
                {
                    "visits": [
                        {
                            "visit_id": "VIS-001",
                            "date": "2026-01-05",
                            "unrecognized_field": "unauthorized value",
                            "confidence": 0.95,
                        }
                    ]
                }
            )

        service = ExtractionService(llm_client=mock_unknown_fields)
        with self.assertRaises(ExtractionValidationError):
            service.extract_page("doc-001", "file.pdf", 1, "Some clinical text")

    def test_08_prohibited_fields_are_rejected(self) -> None:
        """8. Verify prohibited clinical fields (e.g. tumor_size_change) raise validation error."""
        def mock_prohibited_fields(prompt: str, system_prompt: str) -> str:
            return json.dumps(
                {
                    "imaging_reports": [
                        {
                            "modality": "CT Chest",
                            "report_text": "Non-calcified mass",
                            "tumor_size_change": "increased",  # Prohibited clinical interpretation
                            "confidence": 0.95,
                        }
                    ]
                }
            )

        service = ExtractionService(llm_client=mock_prohibited_fields)
        with self.assertRaises(ExtractionValidationError):
            service.extract_page("doc-001", "file.pdf", 1, "Some clinical text")

    def test_09_malformed_llm_json_is_handled(self) -> None:
        """9. Verify non-JSON LLM responses raise ExtractionParseError."""
        def mock_malformed(prompt: str, system_prompt: str) -> str:
            return "This is not valid JSON at all: error in generation {"

        service = ExtractionService(llm_client=mock_malformed)
        with self.assertRaises(ExtractionParseError):
            service.extract_page("doc-001", "file.pdf", 1, "Some clinical text")

    def test_10_missing_ollama_connection_produces_clear_error(self) -> None:
        """10. Verify attempting to call an unreachable Ollama server raises OllamaConnectionError."""
        # Use an invalid port to guarantee immediate connection failure without external call
        service = ExtractionService(base_url="http://127.0.0.1:59999", timeout=1.0)
        with self.assertRaises(OllamaConnectionError) as ctx:
            service.extract_page("doc-001", "file.pdf", 1, "Sample text")
        self.assertIn("Could not connect to Ollama", str(ctx.exception))
        self.assertIn("127.0.0.1:59999", str(ctx.exception))

    def test_11_extraction_prompt_safety_rules(self) -> None:
        """11. Verify extraction system prompt explicitly contains all prohibited interpretation rules."""
        self.assertIn("Extract only facts explicitly written", EXTRACTION_SYSTEM_PROMPT)
        self.assertIn("Do not infer, interpret, diagnose, predict, recommend, or summarize clinically", EXTRACTION_SYSTEM_PROMPT)

        prohibited_rules = [
            "Cancer stage",
            "Prognosis",
            "progression",
            "Treatment response",
            "severity",
            "risk score",
            "Treatment recommendation",
            "Medication recommendation",
            "Normal/abnormal interpretation",
        ]
        for rule in prohibited_rules:
            self.assertIn(
                rule.lower(),
                EXTRACTION_SYSTEM_PROMPT.lower(),
                f"Missing prohibited safety rule '{rule}' in extraction prompt",
            )

    @unittest.skipUnless(os.getenv("RUN_LLM_TESTS") == "1", "Live LLM test skipped unless RUN_LLM_TESTS=1")
    def test_live_doc_003_extraction(self) -> None:
        """12. Live extraction integration test on doc-003.json (requires RUN_LLM_TESTS=1)."""
        doc_003_path = Path("data/extracted/doc-003.json")
        self.assertTrue(doc_003_path.is_file(), f"Missing {doc_003_path}")
        doc_data = json.loads(doc_003_path.read_text(encoding="utf-8"))

        service = ExtractionService()
        result = service.extract_document(doc_data)

        self.assertEqual(result["document_id"], "doc-003")
        self.assertEqual(result["file_name"], "doc-003_laboratory_report_2026-01-10.pdf")
        self.assertEqual(result["pages_processed"], 1)
        self.assertIn("facts", result)

        # Verify laboratory results exist and provenance is valid
        labs = result["facts"].get("laboratory_results", [])
        self.assertGreater(len(labs), 0, "No laboratory results extracted from doc-003")
        for lab in labs:
            self.assertTrue(lab["test_name"])
            self.assertTrue(lab["value"])
            self.assertEqual(lab["source"]["document_id"], "doc-003")
            self.assertEqual(lab["source"]["file_name"], "doc-003_laboratory_report_2026-01-10.pdf")
            self.assertEqual(lab["source"]["page_number"], 1)
            self.assertGreaterEqual(lab["confidence"], 0.0)
            self.assertLessEqual(lab["confidence"], 1.0)


if __name__ == "__main__":
    unittest.main()
