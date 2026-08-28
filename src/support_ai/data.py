from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class DatasetError(ValueError):
    """Raised when the supplied mock dataset is malformed."""


@dataclass(frozen=True)
class Dataset:
    tickets: list[dict[str, Any]]
    accounts: list[dict[str, Any]]

    @classmethod
    def load(cls, data_dir: Path) -> "Dataset":
        tickets = _load_list(data_dir / "tickets.json", "tickets")
        accounts = _load_list(data_dir / "accounts.json", "accounts")
        _validate_unique_ids(tickets, "ticket_id", "tickets")
        _validate_unique_ids(accounts, "account_id", "accounts")
        return cls(tickets=tickets, accounts=accounts)

    @property
    def account_map(self) -> dict[str, dict[str, Any]]:
        return {a["account_id"]: a for a in self.accounts}

    @property
    def dataset_as_of(self) -> datetime:
        if not self.tickets:
            raise DatasetError("tickets.json contains no tickets")
        return max(parse_datetime(t["created_at"]) for t in self.tickets)

    def account_tickets(
        self,
        account_id: str,
        days: int = 90,
        as_of: datetime | None = None,
    ) -> list[dict[str, Any]]:
        if days <= 0:
            raise ValueError("days must be positive")
        reference = as_of or self.dataset_as_of
        cutoff = reference - timedelta(days=days)
        return sorted(
            [
                t for t in self.tickets
                if t.get("account_id") == account_id
                and parse_datetime(t["created_at"]) >= cutoff
                and parse_datetime(t["created_at"]) <= reference
            ],
            key=lambda t: t["created_at"],
            reverse=True,
        )


def _load_list(path: Path, label: str) -> list[dict[str, Any]]:
    try:
        with path.open(encoding="utf-8") as f:
            value = json.load(f)
    except FileNotFoundError as exc:
        raise DatasetError(f"Required {label} file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DatasetError(f"Invalid JSON in {label} file: {path}") from exc
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise DatasetError(f"{label} must be a JSON array of objects: {path}")
    return value


def _validate_unique_ids(items: list[dict[str, Any]], field: str, label: str) -> None:
    missing = [i for i, item in enumerate(items) if not item.get(field)]
    if missing:
        raise DatasetError(f"{label} entries missing {field}: indexes {missing[:5]}")
    ids = [item[field] for item in items]
    if len(ids) != len(set(ids)):
        raise DatasetError(f"Duplicate {field} values found in {label}")


def parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise DatasetError(f"Invalid ISO-8601 datetime: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise DatasetError(f"Invalid ISO date: {value!r}") from exc
