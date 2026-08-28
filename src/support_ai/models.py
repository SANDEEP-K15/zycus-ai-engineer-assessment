from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Category = Literal[
    "Bug", "Feature Request", "How-To", "Performance",
    "Billing", "Integration", "Onboarding", "Data Loss",
]
Urgency = Literal["P1", "P2", "P3", "P4"]


class TicketRequest(BaseModel):
    """Public Task 1 input contract: free text or subject/body JSON."""

    model_config = ConfigDict(extra="forbid")

    text: str | None = Field(default=None, min_length=1, max_length=20_000)
    subject: str | None = Field(default=None, max_length=1_000)
    body: str | None = Field(default=None, max_length=20_000)

    @model_validator(mode="after")
    def validate_input(self) -> "TicketRequest":
        has_text = bool(self.text and self.text.strip())
        has_subject_body = bool((self.subject and self.subject.strip()) or (self.body and self.body.strip()))
        if has_text == has_subject_body:
            raise ValueError("provide either text, or subject/body")
        if not has_text and not (self.subject or self.body):
            raise ValueError("subject or body is required")
        return self

    def to_ticket(self) -> dict[str, str]:
        if self.text:
            return {"subject": "", "body": self.text.strip()}
        return {
            "subject": (self.subject or "").strip(),
            "body": (self.body or "").strip(),
        }


class KnownIssue(BaseModel):
    matched: bool
    document: str | None = None
    section: str | None = None
    evidence: str | None = None
    confidence: float = Field(ge=0, le=1)


class TriageResult(BaseModel):
    product_area: str
    category: Category
    urgency: Urgency
    reasoning: str
    known_issue: KnownIssue
    responder_team: str
    draft_response: str


class RiskFlag(BaseModel):
    ticket_id: str
    signal: str
    quote: str
    severity: Literal["high", "medium", "low"]


class AccountBrief(BaseModel):
    account_id: str
    company: str
    executive_summary: list[str] = Field(min_length=3, max_length=5)
    open_risks_and_flagged_issues: list[str]
    churn_risk_flags: list[RiskFlag]
    talking_points: list[str]
    ticket_count_90d: int = Field(ge=0)
    open_ticket_count_90d: int = Field(ge=0)
