from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .data import Dataset, parse_date
from .models import AccountBrief, RiskFlag


CHURN_TERMS = (
    "cancel", "cancellation", "churn", "competitor", "competing vendor",
    "leaving", "terminate", "termination", "switch vendor", "replace",
)
ESCALATION_TERMS = (
    "escalat", "business continuity", "critical", "urgent", "urgently",
    "immediately", "not acceptable", "unhappy", "frustrat", "executive",
)


def _sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", normalized) if s.strip()]


def _quote_for_ticket(ticket: dict[str, Any]) -> tuple[str, str] | None:
    body = str(ticket.get("body", ""))
    for sentence in _sentences(body):
        lowered = sentence.lower()
        if any(term in lowered for term in CHURN_TERMS):
            return "Potential churn signal", sentence[:280]
    for sentence in _sentences(body):
        lowered = sentence.lower()
        if any(term in lowered for term in ESCALATION_TERMS):
            return "Potential escalation signal", sentence[:280]
    if ticket.get("urgency") == "P1":
        for sentence in _sentences(body):
            if any(term in sentence.lower() for term in ("impact", "blocked", "affected", "missing", "failing")):
                return "P1 incident requiring TAM attention", sentence[:280]
    return None


def build_account_brief(dataset: Dataset, account_id: str, as_of: datetime | None = None) -> AccountBrief:
    account = dataset.account_map.get(account_id)
    if account is None:
        raise KeyError(f"Account {account_id} was not found in accounts.json")

    tickets = dataset.account_tickets(account_id, days=90, as_of=as_of)
    open_tickets = [t for t in tickets if t.get("status") in {"Open", "In Progress", "Pending Customer"}]
    csats = [t["satisfaction_score"] for t in tickets if t.get("satisfaction_score") is not None]
    avg_csat = sum(csats) / len(csats) if csats else None

    flags: list[RiskFlag] = []
    for ticket in tickets:
        signal = _quote_for_ticket(ticket)
        if signal:
            signal_name, quote = signal
            high = signal_name.startswith("Potential churn") or ticket.get("urgency") == "P1"
            flags.append(
                RiskFlag(
                    ticket_id=ticket["ticket_id"],
                    signal=signal_name,
                    quote=quote,
                    severity="high" if high else "medium",
                )
            )

    renewal = parse_date(account["renewal_date"])
    reference_date = (as_of or dataset.dataset_as_of).date()
    days_to_renewal = (renewal - reference_date).days
    seat_utilization = account["seats_active"] / account["seats_licensed"] if account["seats_licensed"] else 0.0

    summary = [
        f"{account['company']} is a {account['plan_tier']} account with ${account['arr_usd']:,} ARR and a recorded health status of {account['health_status']}.",
        f"Usage is {account['usage_trend'].lower()}, with {account['seats_active']} of {account['seats_licensed']} licensed seats active ({seat_utilization:.0%} utilization).",
        f"There are {len(tickets)} tickets in the dataset-relative last 90 days, including {len(open_tickets)} currently open, in-progress, or pending items.",
        f"Renewal is {days_to_renewal} days from the dataset reference date; the account has {len(account.get('escalation_notes', []))} escalation note(s).",
    ]
    if avg_csat is not None:
        summary.append(f"Observed ticket CSAT averages {avg_csat:.1f}/5 across {len(csats)} rated tickets.")

    risks: list[str] = []
    if account["health_status"] in {"At Risk", "Churning"}:
        risks.append(f"Account health is {account['health_status']} with usage trend {account['usage_trend']}.")
    if account["usage_trend"] in {"Declining", "Inactive"}:
        risks.append(f"Usage trend is {account['usage_trend']}.")
    if seat_utilization < 0.5:
        risks.append(f"Active-seat utilization is low at {seat_utilization:.0%}.")
    if account.get("nps_score") is not None and account["nps_score"] <= 6:
        risks.append(f"Recorded NPS is {account['nps_score']}/10, indicating negative or neutral sentiment.")
    if account.get("p1_tickets_last_30d", 0) > 0:
        risks.append(f"Account reports {account['p1_tickets_last_30d']} P1 ticket(s) in the last 30 days.")
    if days_to_renewal <= 60:
        risks.append(f"Renewal is only {days_to_renewal} days away.")
    if open_tickets:
        risks.append(f"{len(open_tickets)} recent ticket(s) remain open, in progress, or pending customer response.")
    for note in account.get("escalation_notes", []):
        risks.append(f"Account escalation note: {note}")
    if flags:
        risks.append(f"{len(flags)} ticket-level churn/escalation signal(s) require TAM attention.")
    if not risks:
        risks.append("No material risk signal was detected by the deterministic rules from the available data.")

    talking_points = [
        f"Review {len(open_tickets)} unresolved recent ticket(s) and confirm ownership/next action.",
        f"Discuss the {account['usage_trend'].lower()} usage trend and active-seat adoption ({account['seats_active']}/{account['seats_licensed']}).",
        f"Review renewal timing ({account['renewal_date']}) and commercial risks before the next QBR.",
    ]
    if account.get("escalation_notes"):
        talking_points.append("Address the latest escalation notes explicitly and confirm whether executive follow-up is needed.")
    if account.get("nps_score") is not None:
        talking_points.append(f"Discuss the recorded NPS score of {account['nps_score']} and ask what would improve the relationship.")
    if flags:
        talking_points.append("Review each ticket-level escalation/churn signal and confirm an owner and next action.")

    return AccountBrief(
        account_id=account_id,
        company=account["company"],
        executive_summary=summary[:5],
        open_risks_and_flagged_issues=risks,
        churn_risk_flags=flags,
        talking_points=talking_points,
        ticket_count_90d=len(tickets),
        open_ticket_count_90d=len(open_tickets),
    )
