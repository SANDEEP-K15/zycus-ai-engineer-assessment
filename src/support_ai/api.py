from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .config import Settings
from .data import Dataset
from .health import build_account_brief
from .llm import GeminiClient
from .models import AccountBrief, TicketRequest, TriageResult
from .retrieval import KnowledgeBase
from .triage import triage_ticket


settings = Settings.from_env()
dataset = Dataset.load(settings.data_dir)
kb = KnowledgeBase(settings.kb_dir)
llm = GeminiClient(settings.gemini_api_key, settings.gemini_model) if settings.gemini_api_key else None
app = FastAPI(title="Support AI", version="1.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "llm_mode": "gemini" if llm else "deterministic-test-mode"}


@app.post("/triage", response_model=TriageResult)
def triage(payload: TicketRequest) -> TriageResult:
    return triage_ticket(payload.to_ticket(), kb, llm)


@app.get("/accounts/{account_id}/brief", response_model=AccountBrief)
def account_brief(account_id: str) -> AccountBrief:
    try:
        return build_account_brief(dataset, account_id, settings.as_of)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
