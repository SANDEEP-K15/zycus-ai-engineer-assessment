from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import Settings
from .data import Dataset
from .eval import run_evaluation, write_report
from .health import build_account_brief
from .llm import GeminiClient
from .models import TicketRequest
from .retrieval import KnowledgeBase
from .triage import triage_ticket


def _llm(settings: Settings) -> GeminiClient | None:
    return GeminiClient(settings.gemini_api_key, settings.gemini_model) if settings.gemini_api_key else None


def _triage_input(args: argparse.Namespace, dataset: Dataset) -> dict[str, str]:
    sources = sum(bool(value) for value in (args.ticket_id, args.text, args.json))
    if sources != 1:
        raise ValueError("triage requires exactly one of --ticket-id, --text, or --json")
    if args.ticket_id:
        try:
            ticket = next(t for t in dataset.tickets if t["ticket_id"] == args.ticket_id)
        except StopIteration as exc:
            raise ValueError(f"Ticket {args.ticket_id} was not found in tickets.json") from exc
        # triage_ticket itself ignores historical labels; only pass raw content here.
        return {"subject": ticket.get("subject", ""), "body": ticket.get("body", "")}
    if args.text:
        return {"subject": "", "body": args.text}
    try:
        payload = json.loads(args.json)
        return TicketRequest.model_validate(payload).to_ticket()
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"invalid triage JSON: {exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(prog="support-ai")
    sub = parser.add_subparsers(dest="command", required=True)
    t = sub.add_parser("triage")
    group = t.add_mutually_exclusive_group(required=True)
    group.add_argument("--ticket-id")
    group.add_argument("--text")
    group.add_argument("--json")
    a = sub.add_parser("account")
    a.add_argument("account_id")
    e = sub.add_parser("eval")
    e.add_argument("--output", default="eval_report.json")
    args = parser.parse_args()

    settings = Settings.from_env()
    dataset = Dataset.load(settings.data_dir)
    kb = KnowledgeBase(settings.kb_dir)

    try:
        if args.command == "triage":
            ticket = _triage_input(args, dataset)
            result = triage_ticket(ticket, kb, _llm(settings))
            print(json.dumps(result.model_dump(), indent=2))
        elif args.command == "account":
            result = build_account_brief(dataset, args.account_id, settings.as_of)
            print(json.dumps(result.model_dump(), indent=2))
        elif args.command == "eval":
            report = run_evaluation(dataset, kb, settings.as_of)
            write_report(report, Path(args.output))
            print(json.dumps(report["summary"], indent=2))
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
