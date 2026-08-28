# Support AI — Intelligent Triage & TAM Account Health

Production-oriented implementation for the Zycus AI Engineer assessment. The solution uses **only the supplied synthetic tickets, account summaries, and knowledge base**.

## What is included

- **Task 1:** raw-ticket triage with local KB retrieval, optional Gemini structured generation, schema validation, evidence checks, and a deterministic offline fallback.
- **Task 2:** deterministic 90-day TAM account brief with account-health signals and direct ticket quotes for ticket-level churn/escalation flags.
- **Task 3:** 6 evaluation cases for each task, including adversarial cases, per-case 0–1 scores, and a JSON report.
- **Task 4:** production design note covering failure modes, latency/quality, data sensitivity, and scaling.
- **Bonus:** GitHub Actions evaluation on every push/PR (+2) and prompt version tracking/changelog (+2).

## Architecture

```text
Task 1
Raw text / {subject, body}
        |
        v
Input validation + normalization
        |
        v
Local TF-IDF retrieval over supplied KB
        |
        +------------------------------+
        |                              |
        v                              v
Gemini structured output        Deterministic fallback
        |                              |
        +--------------+---------------+
                       v
               Pydantic validation
                       |
                       v
                TriageResult

Task 2
Account ID
   |
   +--> accounts.json
   |
   +--> tickets.json -- last 90 days relative to dataset reference date
   |
   v
Deterministic health/risk signals + direct ticket evidence
   |
   v
AccountBrief
```

The retrieval corpus is the provided `knowledge-base/` only. Documents are split on horizontal rules and preserve document/section metadata, following `DATA_SCHEMA.md`.

## Setup

Requires Python 3.11+.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

For live LLM mode:

```bash
copy .env.example .env
# macOS/Linux: cp .env.example .env
# Set GEMINI_API_KEY in .env
```

Environment variables:

- `GEMINI_API_KEY` — required only for live Task 1 LLM mode.
- `GEMINI_MODEL` — optional; defaults to `gemini-2.5-flash`.
- `SUPPORT_AI_AS_OF` — optional ISO-8601 reference timestamp for reproducible Task 2 windows. If omitted, the latest supplied ticket timestamp is used.

Without `GEMINI_API_KEY`, Task 1 runs in deterministic fallback mode so the project can be evaluated without external credentials.

## Single entry point

```bash
support-ai triage --ticket-id TKT-10050
support-ai triage --text "We have a critical outage affecting all users."
support-ai triage --json '{"subject":"How do I configure SSO?","body":"Please help."}'
support-ai account ACC-7397
support-ai eval
```

The `triage` command accepts either free text, JSON containing `subject`/`body`, or one of the supplied dataset ticket IDs. Historical category, urgency, and product-area labels are not used as triage inputs.

## REST API

```bash
uvicorn support_ai.api:app --host 0.0.0.0 --port 8000
```

Endpoints:

- `GET /health`
- `POST /triage` with either `{ "text": "..." }` or `{ "subject": "...", "body": "..." }`
- `GET /accounts/{account_id}/brief`

The API validates request size and shape with Pydantic and rejects unknown input fields.

## Sample Task 1

```bash
support-ai triage --ticket-id TKT-10050
```

The raw ticket text describes a scope error. The supplied authentication/SSO knowledge base contains a matching `403 Forbidden: insufficient_scope` reference, so the fallback or LLM path can surface that evidence without copying the historical ticket labels.

## Sample Task 2

```bash
support-ai account ACC-7397
```

The account pipeline joins by `account_id`, filters ticket history to the last 90 days, and uses deterministic signals for usage, renewal timing, escalation notes, P1 history, NPS, open tickets, and ticket-level escalation/churn evidence.

The default reference date is the latest supplied ticket timestamp. This keeps the historical assessment reproducible instead of making the 90-day window depend on the day the evaluator runs the repository.

## Evaluation

```bash
pytest -q
python scripts/run_eval.py
```

The evaluation report is written to `eval_report.json` and contains per-case pass/fail, passed/total checks, quality scores from 0–1, errors, and aggregate task scores.

The harness deliberately passes only raw `subject`/`body` into Task 1, and includes a prompt-injection adversarial case plus a true no-ticket account case for Task 2.

## Security and reliability

- No API credentials are committed; `.env` is ignored and `.env.example` contains placeholders only.
- Customer text is treated as untrusted data in the LLM prompt; embedded instructions are not followed.
- Common identifiers, email addresses, phone numbers, and secret-like values are redacted before the Gemini boundary.
- Gemini calls use structured JSON output, a 30-second client timeout, one retry, and post-validation of the cited KB document/section.
- LLM reasoning is constrained to a short decision rationale rather than requesting hidden chain-of-thought.
- The deterministic fallback never copies historical category/urgency/product-area labels.
- Account joins tolerate missing `account_id` references as required by the supplied schema.

## Engineering decisions

1. **Local retrieval first.** The supplied KB has nine documents, so a local TF-IDF index is sufficient and avoids unnecessary vector-database infrastructure. The retrieval interface is isolated so embeddings/reranking can be introduced later.
2. **LLM only where it adds value.** Task 1 uses an LLM for contextual classification, reasoning, routing, and response drafting. Task 2 is deterministic because the assignment requires repeatable output for the same input.
3. **Evidence over historical labels.** Existing ticket labels are treated as historical metadata, not ground truth. Task 1 evaluation strips them from the input.
4. **Dataset-relative time.** The supplied data is historical. The default account-health reference is the latest supplied ticket timestamp, with an explicit environment override for reproducibility.
5. **Fail closed on unsupported KB citations.** A generated known issue must point to a document/section actually supplied to the model.

## Limitations

- TF-IDF retrieval is lexical and can miss semantically equivalent wording; embeddings/reranking would be the next retrieval upgrade.
- The live LLM path requires Gemini availability and quota; the deterministic fallback is intentionally less expressive.
- PII redaction covers common patterns, not every possible sensitive-data format. A production deployment should use an enterprise DLP/redaction service and provider retention controls.
- The TAM summarizer is deterministic and template-driven rather than generative, prioritizing reproducibility over prose quality.
- Production deployment would add centralized logs/metrics, persistent indexing, rate limiting, authentication, and distributed tracing.

## Loom walkthrough — recommended 5–6 minutes

1. **0:00–0:45:** Explain the assessment requirements and repository structure.
2. **0:45–2:00:** Walk through Task 1: raw input, retrieval, structured output, validation, and sample ticket.
3. **2:00–3:15:** Walk through Task 2: account join, 90-day window, deterministic risk rules, and direct ticket quotes.
4. **3:15–4:30:** Run the evaluation harness and show the JSON report.
5. **4:30–5:30:** Explain retrieval, determinism, security, and production failure modes.
6. **5:30–6:00:** Show clean setup/entry point and summarize limitations/future work.

## Design note

See [`docs/design-note.md`](docs/design-note.md).
