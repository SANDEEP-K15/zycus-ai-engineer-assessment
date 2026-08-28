from pathlib import Path

import pytest

from support_ai.data import Dataset, parse_datetime
from support_ai.health import build_account_brief

ROOT = Path(__file__).parents[1]
DS = Dataset.load(ROOT / "data")
AS_OF = parse_datetime("2026-05-22T00:00:00Z")


def test_brief_has_required_sections() -> None:
    out = build_account_brief(DS, DS.accounts[0]["account_id"], AS_OF)
    assert 3 <= len(out.executive_summary) <= 5
    assert isinstance(out.open_risks_and_flagged_issues, list)
    assert isinstance(out.talking_points, list)


def test_flags_have_direct_ticket_quotes() -> None:
    out = build_account_brief(DS, "ACC-1785", AS_OF)
    assert any(flag.ticket_id == "TKT-10112" for flag in out.churn_risk_flags)
    assert all(flag.quote.strip() for flag in out.churn_risk_flags)
    assert all(flag.quote in next(t["body"] for t in DS.tickets if t["ticket_id"] == flag.ticket_id).replace("\n", " ") or flag.quote.replace(" ", "") in next(t["body"] for t in DS.tickets if t["ticket_id"] == flag.ticket_id).replace("\n", " ").replace(" ", "") for flag in out.churn_risk_flags)


def test_deterministic_same_input() -> None:
    aid = DS.accounts[0]["account_id"]
    assert build_account_brief(DS, aid, AS_OF).model_dump() == build_account_brief(DS, aid, AS_OF).model_dump()


def test_no_ticket_account_is_valid() -> None:
    aid = next(a["account_id"] for a in DS.accounts if not any(t["account_id"] == a["account_id"] for t in DS.tickets))
    out = build_account_brief(DS, aid, AS_OF)
    assert out.ticket_count_90d == 0
    assert out.open_ticket_count_90d == 0
    assert out.churn_risk_flags == []


def test_renewal_risk_is_reported() -> None:
    out = build_account_brief(DS, "ACC-2944", AS_OF)
    assert any("Renewal is" in risk for risk in out.open_risks_and_flagged_issues)


def test_unknown_account_raises() -> None:
    with pytest.raises(KeyError):
        build_account_brief(DS, "ACC-NOT-REAL", AS_OF)
