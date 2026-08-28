from __future__ import annotations

import re
from typing import Any

from .llm import GeminiClient
from .models import KnownIssue, TriageResult
from .retrieval import KnowledgeBase


TEAM_MAP = {
    "Billing": "Billing Support",
    "Integration": "Integrations Support",
    "Onboarding": "Onboarding Support",
    "Performance": "Platform Reliability Support",
    "Data Loss": "Data Reliability Support",
    "Bug": "Product Support Engineering",
    "How-To": "Technical Support",
    "Feature Request": "Product Support / Product Management",
}

PRODUCTS = (
    "DataBridge Pro", "CloudSync", "AnalyticsHub", "SecureVault", "WorkflowEngine",
)

PRODUCT_AREAS = (
    "Data Sources", "Pipeline Monitoring", "Key Management", "Error Handling",
    "Conflict Resolution", "Permissions", "Exports", "Reports", "Dashboard",
    "Alerts", "Scheduling", "Templates", "Authentication", "API", "Encryption",
    "SSO", "Bandwidth Limits", "File Sync", "Schema Management", "Connectors",
    "Integrations", "Data Ingestion", "Actions", "Triggers", "Audit Logs",
)

ERROR_CODE_PATTERN = re.compile(
    r"\b(?:ERR_[A-Z0-9_]+|[A-Z][A-Z0-9_]{4,}_[A-Z0-9_]+|\d{3}\s+Forbidden)\b"
)


def _ticket_text(ticket: dict[str, Any]) -> str:
    return f"{ticket.get('subject', '')}\n{ticket.get('body', '')}".strip()


def _infer_product_area(text: str, category: str, evidence: Any | None) -> str:
    lowered = text.lower()
    for area in PRODUCT_AREAS:
        if re.search(rf"\b{re.escape(area.lower())}\b", lowered):
            return area
    if category in {"Billing", "Onboarding"}:
        return category
    if evidence and evidence.section:
        section = evidence.section.strip()
        for area in PRODUCT_AREAS:
            if re.search(rf"\b{re.escape(area.lower())}\b", section.lower()):
                return area
    return "General Support"


def _classify_category(text: str) -> str:
    lowered = text.lower()
    if any(p in lowered for p in ("feature request", "would this be on the roadmap", "we'd love to see", "we would love to see")):
        return "Feature Request"
    if any(p in lowered for p in ("invoice", "billing", "charged for", "credit if applicable", "upgrade request", "move from", "moving from")):
        return "Billing"
    if any(p in lowered for p in ("new team member", "new joiner", "onboarding", "training materials", "rollout")):
        return "Onboarding"
    if any(p in lowered for p in ("how do i", "best practice", "how can i", "configuration guide", "configure")):
        return "How-To"
    if any(p in lowered for p in ("missing data", "missing records", "data loss", "data discrepancy", "corrupt", "corrupted")):
        return "Data Loss"
    if any(p in lowered for p in ("slow", "seconds", "timing out", "timeout", "performance degradation", "latency")):
        return "Performance"
    if any(p in lowered for p in ("integration issue", "webhook", "oauth", "sso", "integrate", "authentication errors")):
        return "Integration"
    return "Bug"


def _classify_urgency(text: str) -> str:
    lowered = text.lower()
    explicit_p1 = bool(re.search(r"\bp1\b", lowered))
    critical = any(p in lowered for p in ("business continuity", "business stopped", "critical issue", "critical", "production outage"))
    urgent = any(p in lowered for p in ("urgent", "urgently", "immediately", "asap"))
    impact_match = re.search(r"(?:impacting|blocked|affected users|people blocked)\D{0,30}(\d+)", lowered)
    affected = int(impact_match.group(1)) if impact_match else 0
    seconds = [int(x) for x in re.findall(r"(?:over|taking|loads?\s+are\s+taking)\s*(\d+)\s*seconds", lowered)]
    severe_latency = any(x >= 90 for x in seconds)

    if explicit_p1 or "business continuity" in lowered or "business stopped" in lowered or ("403 forbidden" in lowered and "all users" in lowered):
        return "P1"
    if critical and (affected >= 100 or "all users" in lowered or "production" in lowered):
        return "P1"
    if ("403 forbidden" in lowered and "all users" in lowered) or severe_latency or critical or affected >= 300 or (urgent and affected >= 100):
        return "P2"
    if affected >= 50 or "timeout" in lowered or "missing data" in lowered or "missing records" in lowered:
        return "P3"
    return "P4"


def _known_issue(results: list[tuple[Any, float]], text: str) -> KnownIssue:
    if not results:
        return KnownIssue(matched=False, confidence=0.0)

    top_chunk, top_score = results[0]
    exact_codes = {match.group(0) for match in ERROR_CODE_PATTERN.finditer(text)}
    exact_error_match = bool(exact_codes and any(code in top_chunk.text for code in exact_codes))
    generic_section = top_chunk.section.strip().lower() in {"overview", "features", "pricing", "contents"}
    matched = exact_error_match or (top_score >= 0.15 and not generic_section)
    confidence = min(1.0, max(top_score * 2, 0.9 if exact_error_match else 0.0))

    if not matched:
        return KnownIssue(matched=False, confidence=0.0)
    return KnownIssue(
        matched=True,
        document=top_chunk.document,
        section=top_chunk.section,
        evidence=top_chunk.text[:800],
        confidence=round(confidence, 3),
    )


def _draft_response(ticket: dict[str, Any], category: str, known: KnownIssue) -> str:
    product = _extract_product(ticket)
    if known.matched:
        return (
            f"Thanks for reporting this {category.lower()} issue affecting {product or 'the platform'}. "
            f"Our supplied knowledge base has a potentially relevant reference in "
            f"{known.document}, section \"{known.section}\". "
            f"We’ll route this to {TEAM_MAP[category]} for investigation and follow up with next steps."
        )
    return (
        f"Thanks for reporting this {category.lower()} issue affecting {product or 'the platform'}. "
        f"We’ll route it to {TEAM_MAP[category]} for investigation and follow up with next steps."
    )


def _extract_product(ticket: dict[str, Any]) -> str | None:
    text = _ticket_text(ticket).lower()
    for product in PRODUCTS:
        if product.lower() in text:
            return product
    return None


def _heuristic_triage(ticket: dict[str, Any], kb: KnowledgeBase) -> TriageResult:
    # Only subject/body participate in classification. Historical category,
    # urgency, and product_area labels are never copied into the decision.
    clean_ticket = {"subject": str(ticket.get("subject", "")), "body": str(ticket.get("body", ""))}
    text = _ticket_text(clean_ticket)
    category = _classify_category(text)
    results = kb.search(text, top_k=4)
    evidence = results[0][0] if results else None
    urgency = _classify_urgency(text)
    known = _known_issue(results, text)
    return TriageResult(
        product_area=_infer_product_area(text, category, evidence),
        category=category,
        urgency=urgency,
        reasoning=(
            "Deterministic fallback classification based on the raw ticket text and retrieved "
            "knowledge-base evidence; historical labels are ignored."
        ),
        known_issue=known,
        responder_team=TEAM_MAP[category],
        draft_response=_draft_response(ticket, category, known),
    )


def triage_ticket(
    ticket: dict[str, Any],
    kb: KnowledgeBase,
    llm: GeminiClient | None = None,
) -> TriageResult:
    # Never send historical labels such as category/urgency/product_area to the
    # model. The public task contract is raw subject/body input.
    clean_ticket = {
        "subject": str(ticket.get("subject", "")),
        "body": str(ticket.get("body", "")),
    }
    text = _ticket_text(clean_ticket)
    if not text:
        raise ValueError("ticket subject or body is required")
    results = kb.search(text, top_k=4)
    evidence = [
        {"document": c.document, "section": c.section, "score": round(score, 4), "text": c.text}
        for c, score in results
    ]
    if llm is None:
        return _heuristic_triage(ticket, kb)
    return llm.triage(clean_ticket, evidence)
