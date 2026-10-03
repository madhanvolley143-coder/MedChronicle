"""Unit tests for multilingual OCR capabilities and Tamil language detection.

Verifies:
10. Tamil OCR capability is detected truthfully:
    - If Tamil language data is missing, the system reports it explicitly.
    - Never falsely claims support for uninstalled languages.
    - Accurately checks available Tesseract languages.
"""

import unittest

from app.services.ocr import OCREngine


class TestMultilingualOCR(unittest.TestCase):
    """Test suite for multilingual OCR language detection and validation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = OCREngine()
        cls.tesseract_ready = cls.engine.is_tesseract_available()

    def test_10a_installed_languages_detection(self) -> None:
        """Verify installed languages are detected from local Tesseract."""
        if not self.tesseract_ready:
            self.skipTest("Tesseract not available on system.")

        langs = self.engine.get_available_languages()
        self.assertIsInstance(langs, list)
        self.assertIn("eng", langs)

    def test_10b_tamil_capability_detection_is_truthful(self) -> None:
        """Verify Tamil language detection is strictly truthful and never faked."""
        if not self.tesseract_ready:
            self.skipTest("Tesseract not available on system.")

        installed = self.engine.get_available_languages()
        has_tamil = "tam" in [l.lower() for l in installed]

        is_valid, msg = self.engine.validate_languages("tam")

        if not has_tamil:
            self.assertFalse(is_valid)
            self.assertIn("tamil", msg.lower())
            self.assertIn("language pack", msg.lower())
        else:
            self.assertTrue(is_valid)

    def test_10c_mixed_language_validation(self) -> None:
        """Verify combined language string (e.g. eng+tam) requires both languages."""
        if not self.tesseract_ready:
            self.skipTest("Tesseract not available on system.")

        installed = self.engine.get_available_languages()
        has_tamil = "tam" in [l.lower() for l in installed]

        is_valid, msg = self.engine.validate_languages("eng+tam")
        if not has_tamil:
            self.assertFalse(is_valid)
            self.assertIn("tamil", msg.lower())
        else:
            self.assertTrue(is_valid)

    def test_10d_nonexistent_language_rejected(self) -> None:
        """Verify unknown or uninstalled language codes are rejected."""
        if not self.tesseract_ready:
            self.skipTest("Tesseract not available on system.")

        is_valid, msg = self.engine.validate_languages("xyz_unknown")
        self.assertFalse(is_valid)
        self.assertIn("not installed", msg.lower())


if __name__ == "__main__":
    unittest.main()
