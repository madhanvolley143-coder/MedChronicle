"""Controlled structured information extraction service for JourneyBrief.

Invokes configured LLM provider (Google Gemini API or local Ollama) to extract
facts from page-level text, attaches application-controlled source provenance,
and validates each clinical fact against strict Pydantic models.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Type

from app.core.config import settings
from app.models import (
    ImagingReport,
    InvestigationRecord,
    LaboratoryResult,
    MedicationRecord,
    PathologyFinding,
    ProcedureRecord,
    ReferralRecord,
    SourceReference,
    TimelineEvent,
    Visit,
)
from app.services.gemini_client import (
    GeminiAPIError,
    GeminiAuthError,
    GeminiClient,
    GeminiError,
    GeminiProvider,
    GeminiTimeoutError,
    LLMProvider,
)
from app.services.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    build_page_extraction_prompt,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Extraction Errors
# ---------------------------------------------------------------------------

class ExtractionError(Exception):
    """Base exception for extraction service errors."""


class OllamaConnectionError(ExtractionError):
    """Raised when connection to local Ollama server fails."""


class OllamaAPIError(ExtractionError):
    """Raised when Ollama returns an HTTP or API error."""


class OllamaTimeoutError(ExtractionError):
    """Raised when Ollama request exceeds the configured timeout."""


class ExtractionParseError(ExtractionError):
    """Raised when LLM response cannot be parsed as JSON."""


class ExtractionValidationError(ExtractionError):
    """Raised when extracted facts fail Pydantic model validation."""


# ---------------------------------------------------------------------------
# LLM Providers
# ---------------------------------------------------------------------------

class OllamaProvider(LLMProvider):
    """LLMProvider implementation for local Ollama HTTP API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.timeout = timeout if timeout is not None else settings.OLLAMA_TIMEOUT

    @property
    def model_name(self) -> str:
        return self.model

    def generate(self, prompt: str, system_prompt: str) -> str:
        endpoint = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.0,
                "num_ctx": 2048,
                "num_predict": 1024,
            },
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
                return resp_data.get("response", "")
        except urllib.error.HTTPError as http_err:
            raise OllamaAPIError(
                f"Ollama returned HTTP error {http_err.code}: {http_err.reason}"
            ) from http_err
        except urllib.error.URLError as url_err:
            raise OllamaConnectionError(
                f"Could not connect to Ollama at '{self.base_url}': {url_err.reason}. "
                "Ensure local Ollama server is running (e.g. run 'ollama serve')."
            ) from url_err
        except TimeoutError as timeout_err:
            raise OllamaTimeoutError(
                f"Ollama request timed out after {self.timeout}s"
            ) from timeout_err
        except Exception as exc:
            raise ExtractionError(f"Unexpected error communicating with Ollama: {exc}") from exc


class CallableProvider(LLMProvider):
    """Wraps a custom callable (prompt, system_prompt) -> str for testing."""

    def __init__(self, fn: Callable[[str, str], str], model_name: str = "mock-model") -> None:
        self.fn = fn
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate(self, prompt: str, system_prompt: str) -> str:
        return self.fn(prompt, system_prompt)


# Map of category keys to their respective Pydantic clinical models
CATEGORY_MODEL_MAP: Dict[str, Type[Any]] = {
    "visits": Visit,
    "pathology_findings": PathologyFinding,
    "laboratory_results": LaboratoryResult,
    "imaging_reports": ImagingReport,
    "medications": MedicationRecord,
    "procedures": ProcedureRecord,
    "referrals": ReferralRecord,
    "investigations": InvestigationRecord,
    "timeline_events": TimelineEvent,
}


def clean_json_response(raw_text: str) -> str:
    """Extract valid JSON from raw LLM output, stripping code fences or prose."""
    cleaned = raw_text.strip()
    # Remove markdown code blocks if present
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    # Find boundaries of the outermost JSON object
    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        cleaned = cleaned[start_idx : end_idx + 1]

    return cleaned


class ExtractionService:
    """Service orchestrating page-by-page LLM extraction and Pydantic validation."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        llm_client: Optional[Callable[[str, str], str]] = None,
        provider: Optional[LLMProvider] = None,
    ) -> None:
        """Initialize extraction service with a configured LLM provider.

        Args:
            base_url: Ollama base URL. Defaults to settings.OLLAMA_BASE_URL.
            model: Model identifier override.
            timeout: Request timeout in seconds.
            llm_client: Optional custom callable (prompt, system_prompt) -> response_str.
            provider: Optional explicit LLMProvider instance (GeminiProvider, OllamaProvider, etc.).
        """
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model
        self.timeout = timeout if timeout is not None else settings.OLLAMA_TIMEOUT
        self.llm_client = llm_client

        if provider is not None:
            self.provider = provider
        elif llm_client is not None:
            self.provider = CallableProvider(llm_client)
        elif base_url is not None:
            self.provider = OllamaProvider(base_url=base_url, model=model, timeout=timeout)
        else:
            # Auto-select based on settings
            if settings.DEFAULT_LLM_PROVIDER == "gemini" and settings.GEMINI_API_KEY:
                self.provider = GeminiProvider(model=model or settings.GEMINI_MODEL)
            else:
                self.provider = OllamaProvider(base_url=base_url, model=model, timeout=timeout)

    def _call_ollama(self, prompt: str, system_prompt: str) -> str:
        """Backwards-compatible helper delegating to configured provider."""
        return self.provider.generate(prompt, system_prompt)

    def extract_page(
        self,
        document_id: str,
        file_name: str,
        page_number: int,
        page_text: str,
    ) -> Dict[str, List[Any]]:
        """Extract and validate facts from a single document page.

        Attaches known provenance (document_id, file_name, page_number) to each fact.
        """
        user_prompt = build_page_extraction_prompt(
            document_id=document_id,
            file_name=file_name,
            page_number=page_number,
            page_text=page_text,
        )

        try:
            raw_response = self.provider.generate(
                prompt=user_prompt,
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
            )
        except (
            OllamaConnectionError,
            OllamaTimeoutError,
            OllamaAPIError,
            GeminiError,
            ExtractionError,
        ):
            raise
        except Exception as exc:
            raise ExtractionError(f"Error during LLM provider generation: {exc}") from exc

        cleaned_json = clean_json_response(raw_response)
        try:
            parsed_data = json.loads(cleaned_json)
        except json.JSONDecodeError as err:
            raise ExtractionParseError(
                f"Failed to parse LLM response as JSON on page {page_number} of {document_id}: {err}\n"
                f"Raw Response: {raw_response[:300]}..."
            ) from err

        if not isinstance(parsed_data, dict):
            raise ExtractionParseError(
                f"LLM returned non-object JSON structure ({type(parsed_data).__name__}) on page {page_number} of {document_id}"
            )

        validated_facts: Dict[str, List[Any]] = {cat: [] for cat in CATEGORY_MODEL_MAP}

        # Validate each fact with its category model
        for category, model_cls in CATEGORY_MODEL_MAP.items():
            items = parsed_data.get(category, [])
            if not isinstance(items, list):
                continue

            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    raise ExtractionValidationError(
                        f"Fact item at {category}[{idx}] on page {page_number} of {document_id} is not an object"
                    )

                # Application constructs SourceReference; LLM cannot control provenance
                text_anchor = item.pop("text_anchor", None)
                # LLM should not supply source; if present, override with verified app provenance
                item.pop("source", None)

                source_ref = SourceReference(
                    document_id=document_id,
                    file_name=file_name,
                    page_number=page_number,
                    text_anchor=text_anchor,
                )

                # Validate confidence
                confidence_val = item.get("confidence", 0.90)
                if not isinstance(confidence_val, (int, float)) or not (0.0 <= confidence_val <= 1.0):
                    raise ExtractionValidationError(
                        f"Invalid confidence '{confidence_val}' in {category}[{idx}] on page {page_number} of {document_id}"
                    )

                item["confidence"] = float(confidence_val)
                item["source"] = source_ref

                try:
                    validated_instance = model_cls.model_validate(item)
                    validated_facts[category].append(validated_instance)
                except Exception as val_err:
                    raise ExtractionValidationError(
                        f"Validation failed for {category}[{idx}] on page {page_number} of {document_id}: {val_err}"
                    ) from val_err

        return validated_facts

    def extract_document(self, doc_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and aggregate validated facts across all pages of a document JSON."""
        document_id = doc_data["document_id"]
        file_name = doc_data["file_name"]
        pages = doc_data.get("pages", [])

        aggregated_facts: Dict[str, List[Dict[str, Any]]] = {
            cat: [] for cat in CATEGORY_MODEL_MAP
        }

        for page in pages:
            page_number = page["page_number"]
            page_text = page["text"]

            page_facts = self.extract_page(
                document_id=document_id,
                file_name=file_name,
                page_number=page_number,
                page_text=page_text,
            )

            for cat, instances in page_facts.items():
                for inst in instances:
                    aggregated_facts[cat].append(inst.model_dump(mode="json"))

        return {
            "document_id": document_id,
            "file_name": file_name,
            "pages_processed": len(pages),
            "facts": aggregated_facts,
        }
