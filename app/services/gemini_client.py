"""Google Gemini client for JourneyBrief Cancer Care structured extraction.

Interacts with the Google Gemini API using google-genai SDK to request
structured JSON extractions, enforcing strict error handling, key sanitization,
and zero clinical interpretation boundaries.
"""

from abc import ABC, abstractmethod
import json
import logging
from typing import Any, Callable, Dict, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base Provider Interface
# ---------------------------------------------------------------------------

class LLMProvider(ABC):
    """Abstract interface for LLM extraction providers."""

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str) -> str:
        """Send prompt and system prompt to LLM and return raw JSON response string."""
        pass


# ---------------------------------------------------------------------------
# Gemini Error Hierarchy
# ---------------------------------------------------------------------------

class GeminiError(Exception):
    """Base exception for all Gemini client errors."""
    pass


class GeminiAuthError(GeminiError):
    """Raised when authentication fails (missing, invalid, or forbidden API key)."""
    pass


class GeminiAPIError(GeminiError):
    """Raised when Gemini returns an API error or empty/malformed payload."""
    pass


class GeminiTimeoutError(GeminiError):
    """Raised when Gemini API request times out."""
    pass


def _sanitize_message(message: str, api_key: Optional[str] = None) -> str:
    """Ensure no API keys are present in error messages or logs."""
    if not message:
        return ""
    sanitized = str(message)
    if api_key and len(api_key) > 4:
        sanitized = sanitized.replace(api_key, "[REDACTED_API_KEY]")
    return sanitized


# ---------------------------------------------------------------------------
# Gemini Client & Provider Implementation
# ---------------------------------------------------------------------------

class GeminiClient:
    """Client for generating structured extractions using Google Gemini API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        client: Optional[Any] = None,
    ) -> None:
        """Initialize Gemini client.

        Args:
            api_key: Optional API key. Defaults to settings.GEMINI_API_KEY.
            model: Optional model name. Defaults to settings.GEMINI_MODEL.
            client: Optional pre-configured genai client (useful for unit tests / mocking).
        """
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self._client = client

    def _get_client(self) -> Any:
        """Lazily initialize genai.Client."""
        if self._client is not None:
            return self._client

        if not self.api_key:
            raise GeminiAuthError(
                "GEMINI_API_KEY is not configured. Set GEMINI_API_KEY in your .env file or environment."
            )

        try:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
            return self._client
        except Exception as exc:
            sanitized = _sanitize_message(str(exc), self.api_key)
            raise GeminiAuthError(f"Failed to initialize Gemini client: {sanitized}") from exc

    def generate(self, prompt: str, system_prompt: str) -> str:
        """Generate structured JSON response from Gemini.

        Args:
            prompt: User extraction prompt containing document context & text.
            system_prompt: System prompt with safety boundaries and schema definitions.

        Returns:
            JSON response string from Gemini.
        """
        if not self.api_key and self._client is None:
            raise GeminiAuthError(
                "GEMINI_API_KEY is not configured. Set GEMINI_API_KEY in your .env file or environment."
            )

        client = self._get_client()

        try:
            from google.genai import types
            from google.genai import errors

            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                temperature=0.0,
            )

            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )

            if response is None or not hasattr(response, "text") or response.text is None:
                raise GeminiAPIError("Empty response received from Gemini API.")

            text = response.text.strip()
            if not text:
                raise GeminiAPIError("Empty text received from Gemini API response.")

            return text

        except GeminiError:
            raise
        except Exception as exc:
            exc_str = str(exc).lower()
            sanitized = _sanitize_message(str(exc), self.api_key)

            # Classify specific error scenarios
            if any(k in exc_str for k in ["api_key", "unauthenticated", "401", "403", "permission_denied", "invalid_argument"]):
                raise GeminiAuthError(f"Gemini authentication/permission error: {sanitized}") from exc
            if any(k in exc_str for k in ["timeout", "timed out", "deadline"]):
                raise GeminiTimeoutError(f"Gemini request timed out: {sanitized}") from exc

            raise GeminiAPIError(f"Gemini API error: {sanitized}") from exc


class GeminiProvider(LLMProvider):
    """LLMProvider implementation backed by GeminiClient."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        client: Optional[Any] = None,
    ) -> None:
        self.gemini_client = GeminiClient(api_key=api_key, model=model, client=client)

    @property
    def model_name(self) -> str:
        return self.gemini_client.model

    def generate(self, prompt: str, system_prompt: str) -> str:
        return self.gemini_client.generate(prompt, system_prompt)
