from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .data import parse_datetime


@dataclass(frozen=True)
class Settings:
    root: Path
    data_dir: Path
    kb_dir: Path
    gemini_api_key: str | None
    gemini_model: str
    as_of: datetime | None

    @classmethod
    def from_env(cls, root: Path | None = None) -> "Settings":
        root = (root or Path(__file__).resolve().parents[2]).resolve()
        load_dotenv(root / ".env")
        raw_as_of = os.getenv("SUPPORT_AI_AS_OF") or None
        as_of = parse_datetime(raw_as_of) if raw_as_of else None
        return cls(
            root=root,
            data_dir=root / "data",
            kb_dir=root / "knowledge-base",
            gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            as_of=as_of,
        )
