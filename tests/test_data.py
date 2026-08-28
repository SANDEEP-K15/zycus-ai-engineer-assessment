from pathlib import Path

import pytest

from support_ai.data import Dataset, DatasetError, parse_datetime

ROOT = Path(__file__).parents[1]


def test_dataset_loads() -> None:
    ds = Dataset.load(ROOT / "data")
    assert len(ds.tickets) == 500
    assert len(ds.accounts) == 50


def test_dataset_reference_date_uses_latest_ticket() -> None:
    ds = Dataset.load(ROOT / "data")
    assert ds.dataset_as_of.isoformat().startswith("2026-05-22")


def test_missing_account_is_safe() -> None:
    ds = Dataset.load(ROOT / "data")
    missing = next(t["account_id"] for t in ds.tickets if t["account_id"] not in ds.account_map)
    assert ds.account_tickets(missing)


def test_account_window_excludes_tickets_after_reference() -> None:
    ds = Dataset.load(ROOT / "data")
    reference = parse_datetime("2026-05-22T00:00:00Z")
    tickets = ds.account_tickets("ACC-3336", days=90, as_of=reference)
    assert all(parse_datetime(t["created_at"]) <= reference for t in tickets)


def test_invalid_datetime_is_rejected() -> None:
    with pytest.raises(DatasetError):
        parse_datetime("not-a-date")
