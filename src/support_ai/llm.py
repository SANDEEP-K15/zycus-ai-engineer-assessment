from __future__ import annotations

import json
import logging
import re
import time
from importlib.resources import files
from typing import Any

from .models import TriageResult

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Raised when the external LLM cannot produce a valid triage result."""


class GeminiClient:
    """
    Gemini-backed triage client.

    The client validates every model response against the application's
    TriageResult schema and ensures that any knowledge-base citation refers
    to retrieved evidence.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
        max_attempts: int = 2,
    ) -> None:
        if not api_key.strip():
            raise ValueError("GEMINI_API_KEY must not be empty")

        if not model.strip():
            raise ValueError("Gemini model must not be empty")

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")

        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=int(timeout_seconds * 1000),
            ),
        )

        self._model = model
        self._max_attempts = max_attempts

    def triage(
        self,
        ticket: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> TriageResult:
        """
        Generate and validate a structured triage result.

        Any knowledge-base citation returned by the LLM must refer to retrieved
        evidence. Equivalent path separators are normalized to avoid rejecting
        an otherwise valid citation.
        """

        schema = TriageResult.model_json_schema()

        safe_ticket = _redact_sensitive(ticket)
        safe_evidence = [
            _redact_sensitive(item)
            for item in evidence
        ]

        base_prompt = _build_prompt(
            safe_ticket,
            safe_evidence,
        )

        allowed_citations = _build_allowed_citations(
            safe_evidence,
        )

        last_error: Exception | None = None

        for attempt in range(self._max_attempts):
            prompt = self._build_attempt_prompt(
                base_prompt=base_prompt,
                allowed_citations=allowed_citations,
                attempt=attempt,
            )

            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=self._types.GenerateContentConfig(
                        temperature=0,
                        response_mime_type="application/json",
                        response_schema=schema,
                    ),
                )

                if not response.text:
                    raise ValueError(
                        "LLM returned an empty response"
                    )

                result = TriageResult.model_validate_json(
                    response.text
                )

                result = self._validate_and_canonicalize_known_issue(
                    result=result,
                    allowed_citations=allowed_citations,
                )

                return result

            except Exception as exc:
                last_error = exc

                logger.warning(
                    "Gemini triage attempt %s/%s failed: %s",
                    attempt + 1,
                    self._max_attempts,
                    exc,
                )

                if attempt + 1 < self._max_attempts:
                    delay_seconds = 0.5 * (2**attempt)

                    logger.info(
                        "Retrying Gemini triage in %.1f seconds",
                        delay_seconds,
                    )

                    time.sleep(delay_seconds)

        raise LLMError(
            f"Gemini triage failed after "
            f"{self._max_attempts} attempt(s)"
        ) from last_error

    @staticmethod
    def _build_attempt_prompt(
        base_prompt: str,
        allowed_citations: list[dict[str, str]],
        attempt: int,
    ) -> str:
        """
        Build the prompt for a generation attempt.

        The first attempt uses the normal versioned prompt. Retry attempts
        explicitly tell the model why the previous response was rejected.
        """

        if attempt == 0:
            return base_prompt

        citation_json = json.dumps(
            allowed_citations,
            indent=2,
            ensure_ascii=False,
        )

        return (
            f"{base_prompt}\n\n"
            "IMPORTANT RETRY CORRECTION:\n"
            "Your previous response was rejected because its output was "
            "invalid or because it cited a knowledge-base document/section "
            "pair that was not present in the retrieved evidence.\n\n"
            "If known_issue.matched is true, document and section MUST refer "
            "to one of the following retrieved citation pairs:\n"
            f"{citation_json}\n\n"
            "Do not invent, rename, shorten, or replace a document path or "
            "section title.\n\n"
            "If none of the retrieved citations directly supports a known "
            "issue, set:\n"
            "- known_issue.matched = false\n"
            "- known_issue.document = null\n"
            "- known_issue.section = null\n"
            "- known_issue.evidence = null\n"
            "- known_issue.confidence = 0.0\n\n"
            "Return only valid JSON conforming to the required schema."
        )

    @staticmethod
    def _validate_and_canonicalize_known_issue(
        result: TriageResult,
        allowed_citations: list[dict[str, str]],
    ) -> TriageResult:
        """
        Validate a matched known issue against retrieved evidence.

        Exact matches are accepted directly. Equivalent document paths using
        different slash styles are canonicalized to the exact retrieved path.

        This does NOT allow invented citations.
        """

        known_issue = result.known_issue

        if not known_issue.matched:
            return result

        if not known_issue.document:
            raise ValueError(
                "LLM marked known_issue as matched but omitted document"
            )

        if not known_issue.section:
            raise ValueError(
                "LLM marked known_issue as matched but omitted section"
            )

        exact_pairs = {
            (
                item["document"],
                item["section"],
            )
            for item in allowed_citations
        }

        citation_pair = (
            known_issue.document,
            known_issue.section,
        )

        if citation_pair in exact_pairs:
            return result

        normalized_document = _normalize_document_path(
            known_issue.document
        )
        normalized_section = _normalize_section(
            known_issue.section
        )

        matches = [
            item
            for item in allowed_citations
            if (
                _normalize_document_path(item["document"])
                == normalized_document
                and _normalize_section(item["section"])
                == normalized_section
            )
        ]

        if len(matches) != 1:
            raise ValueError(
                "LLM cited a document/section not present "
                "in retrieved evidence"
            )

        canonical = matches[0]

        canonical_known_issue = known_issue.model_copy(
            update={
                "document": canonical["document"],
                "section": canonical["section"],
            }
        )

        return result.model_copy(
            update={
                "known_issue": canonical_known_issue,
            }
        )


def _normalize_document_path(path: str) -> str:
    """
    Normalize path separators for comparison only.

    The original retrieved path is preserved in the final result.
    """

    return path.strip().replace("\\", "/")


def _normalize_section(section: str) -> str:
    """Normalize harmless surrounding whitespace for comparison."""

    return " ".join(section.strip().split())


def _build_allowed_citations(
    evidence: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """
    Extract unique valid document/section pairs from retrieved evidence.
    """

    seen: set[tuple[str, str]] = set()
    citations: list[dict[str, str]] = []

    for item in evidence:
        document = item.get("document")
        section = item.get("section")

        if not isinstance(document, str):
            continue

        if not isinstance(section, str):
            continue

        document = document.strip()
        section = section.strip()

        if not document or not section:
            continue

        pair = (
            document,
            section,
        )

        if pair in seen:
            continue

        seen.add(pair)

        citations.append(
            {
                "document": document,
                "section": section,
            }
        )

    return citations


def _build_prompt(
    ticket: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> str:
    """
    Load the versioned triage prompt and inject ticket/evidence context.
    """

    try:
        template = (
            files("support_ai")
            .joinpath("prompts/triage_v1.md")
            .read_text(encoding="utf-8")
        )

    except OSError as exc:
        raise LLMError(
            "Versioned triage prompt could not be loaded"
        ) from exc

    return template.format(
        ticket=json.dumps(
            ticket,
            indent=2,
            ensure_ascii=False,
        ),
        evidence=json.dumps(
            evidence,
            indent=2,
            ensure_ascii=False,
        ),
    )


def _redact_sensitive(value: Any) -> Any:
    """
    Remove common sensitive identifiers before text crosses the LLM boundary.

    Redaction is intentionally conservative. It avoids treating ordinary
    documentation phrases such as:

        "existing token: tokens are immutable"

    as secrets.
    """

    if isinstance(value, dict):
        return {
            key: _redact_sensitive(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            _redact_sensitive(item)
            for item in value
        ]

    if not isinstance(value, str):
        return value

    redacted = value

    # IDs such as TKT-12345, ACC-7397, CASE-123456.
    redacted = re.sub(
        r"\b[A-Z]{2,10}-\d{3,}\b",
        "[REDACTED_ID]",
        redacted,
    )

    # Email addresses.
    redacted = re.sub(
        r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b",
        "[REDACTED_EMAIL]",
        redacted,
    )

    # Phone numbers with common international/local formatting.
    redacted = re.sub(
        r"\+?\d[\d .()\-]{8,}\d",
        "[REDACTED_PHONE]",
        redacted,
    )

    # Explicit secret-bearing field names only.
    #
    # Deliberately DO NOT match the generic word "token" by itself because
    # ordinary documentation frequently uses phrases such as:
    #
    # "token: tokens are immutable"
    #
    # Matching only clearly sensitive key names substantially reduces
    # false-positive corruption of knowledge-base evidence.
    secret_pattern = re.compile(
        r"(?ix)"
        r"\b("
        r"api[_ -]?key"
        r"|access[_ -]?token"
        r"|refresh[_ -]?token"
        r"|auth[_ -]?token"
        r"|authentication[_ -]?token"
        r"|client[_ -]?secret"
        r"|client[_ -]?key"
        r"|private[_ -]?key"
        r"|secret"
        r"|password"
        r")"
        r"\s*[:=]\s*"
        r"([^\s,;]+)"
    )

    redacted = secret_pattern.sub(
        lambda match: (
            f"{match.group(1)}=[REDACTED_SECRET]"
        ),
        redacted,
    )

    return redacted