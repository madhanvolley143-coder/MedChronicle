"""Unit tests for Gemini client and Gemini extraction provider.

Tests all error modes, safety boundaries, schema enforcement, and key sanitization
using deterministic mocked responses without requiring a real API key.
"""

from dataclasses import dataclass
import json
from unittest.mock import MagicMock, patch
import unittest

from app.services.extractor import (
    ExtractionParseError,
    ExtractionService,
    ExtractionValidationError,
)
from app.services.gemini_client import (
    GeminiAPIError,
    GeminiAuthError,
    GeminiClient,
    GeminiError,
    GeminiProvider,
    GeminiTimeoutError,
    _sanitize_message,
)


@dataclass
class MockResponse:
    """Mock Gemini generate_content response."""
    text: str


class TestGeminiClient(unittest.TestCase):
    """Test suite for GeminiClient and GeminiProvider with mocked API."""

    def test_01_valid_structured_response(self) -> None:
        """1. Verify valid structured JSON response from Gemini is processed correctly."""
        mock_payload = {
            "laboratory_results": [
                {
                    "test_name": "Hemoglobin",
                    "value": "13.4",
                    "unit": "g/dL",
                    "reference_range_text": "12.0 - 15.5 g/dL",
                    "date": "2026-01-10",
                    "confidence": 0.95,
                }
            ]
        }
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = MockResponse(
            text=json.dumps(mock_payload)
        )

        gemini_client = GeminiClient(api_key="mock-api-key", model="gemini-2.5-flash", client=mock_client)
        resp_text = gemini_client.generate("Extract clinical data", "System instructions")

        self.assertIsInstance(resp_text, str)
        parsed = json.loads(resp_text)
        self.assertIn("laboratory_results", parsed)
        self.assertEqual(parsed["laboratory_results"][0]["test_name"], "Hemoglobin")

        # Test within ExtractionService using GeminiProvider
        provider = GeminiProvider(api_key="mock-api-key", client=mock_client)
        service = ExtractionService(provider=provider)
        facts = service.extract_page(
            document_id="doc-003",
            file_name="doc-003.pdf",
            page_number=1,
            page_text="Sample text",
        )
        self.assertEqual(len(facts["laboratory_results"]), 1)
        lab = facts["laboratory_results"][0]
        self.assertEqual(lab.test_name, "Hemoglobin")
        self.assertEqual(lab.source.document_id, "doc-003")
        self.assertEqual(lab.source.page_number, 1)

    def test_02_malformed_json_response(self) -> None:
        """2. Verify malformed JSON output from Gemini raises ExtractionParseError."""
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = MockResponse(
            text="This is not valid JSON at all: { broken json ... "
        )

        provider = GeminiProvider(api_key="mock-api-key", client=mock_client)
        service = ExtractionService(provider=provider)

        with self.assertRaises(ExtractionParseError) as ctx:
            service.extract_page(
                document_id="doc-003",
                file_name="doc-003.pdf",
                page_number=1,
                page_text="Sample text",
            )
        self.assertIn("Failed to parse LLM response as JSON", str(ctx.exception))

    def test_03_empty_response(self) -> None:
        """3. Verify empty or whitespace response from Gemini raises GeminiAPIError."""
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = MockResponse(text="")

        gemini_client = GeminiClient(api_key="mock-api-key", client=mock_client)
        with self.assertRaises(GeminiAPIError) as ctx:
            gemini_client.generate("Prompt", "System prompt")
        self.assertIn("Empty", str(ctx.exception))

    def test_04_api_error_handling(self) -> None:
        """4. Verify Gemini API error raises GeminiAPIError and sanitizes keys."""
        fake_secret = "AIzaSySecretFakeApiKey123456"
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception(
            f"Quota exceeded for key {fake_secret}"
        )

        gemini_client = GeminiClient(api_key=fake_secret, client=mock_client)
        with self.assertRaises(GeminiError) as ctx:
            gemini_client.generate("Prompt", "System prompt")

        error_msg = str(ctx.exception)
        self.assertNotIn(fake_secret, error_msg)
        self.assertIn("[REDACTED_API_KEY]", error_msg)

    def test_05_timeout_handling(self) -> None:
        """5. Verify timeout in Gemini API call raises GeminiTimeoutError."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = TimeoutError("Deadline exceeded after 30s")

        gemini_client = GeminiClient(api_key="mock-key", client=mock_client)
        with self.assertRaises(GeminiTimeoutError) as ctx:
            gemini_client.generate("Prompt", "System prompt")
        self.assertIn("timed out", str(ctx.exception).lower())

    def test_06_missing_api_key_raises_auth_error(self) -> None:
        """6. Verify missing API key raises GeminiAuthError without attempting network call."""
        with patch("app.services.gemini_client.settings.GEMINI_API_KEY", None):
            client = GeminiClient(api_key=None, client=None)
            with self.assertRaises(GeminiAuthError) as ctx:
                client.generate("Prompt", "System prompt")
            self.assertIn("GEMINI_API_KEY is not configured", str(ctx.exception))

    def test_07_prohibited_field_response(self) -> None:
        """7. Verify prohibited clinical interpretation fields are rejected by Pydantic."""
        mock_payload = {
            "imaging_reports": [
                {
                    "modality": "CT Chest",
                    "report_text": "Non-calcified mass",
                    "tumor_size_change": "increased",  # Prohibited clinical inference
                    "confidence": 0.95,
                }
            ]
        }
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = MockResponse(
            text=json.dumps(mock_payload)
        )

        provider = GeminiProvider(api_key="mock-key", client=mock_client)
        service = ExtractionService(provider=provider)

        with self.assertRaises(ExtractionValidationError):
            service.extract_page(
                document_id="doc-004",
                file_name="doc-004.pdf",
                page_number=1,
                page_text="Sample text",
            )

    def test_08_invalid_schema_response(self) -> None:
        """8. Verify invalid schema types (e.g. non-numeric confidence or missing fields) fail validation."""
        mock_payload = {
            "laboratory_results": [
                {
                    "test_name": "Hemoglobin",
                    # Missing required 'value' field
                    "unit": "g/dL",
                    "confidence": 1.5,  # Invalid confidence > 1.0
                }
            ]
        }
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = MockResponse(
            text=json.dumps(mock_payload)
        )

        provider = GeminiProvider(api_key="mock-key", client=mock_client)
        service = ExtractionService(provider=provider)

        with self.assertRaises(ExtractionValidationError):
            service.extract_page(
                document_id="doc-003",
                file_name="doc-003.pdf",
                page_number=1,
                page_text="Sample text",
            )


if __name__ == "__main__":
    unittest.main()
