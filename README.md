# Support AI — Intelligent Ticket Triage & TAM Account Health

> A production-oriented AI support system for intelligent support-ticket triage and Technical Account Manager (TAM) account health analysis.

Built for the **Zycus AI Engineer Assessment**, this project combines knowledge-base retrieval, structured LLM generation, deterministic business logic, schema validation, automated evaluation, and production-oriented engineering practices.

The core design principle is simple:

> **Use AI where contextual reasoning adds value, and deterministic logic where reproducibility and explainability matter most.**

---

## Overview

The system addresses two core support-engineering workflows.

### Task 1 — Intelligent Ticket Triage

Given a raw support ticket, the system:

- Validates and normalizes the input.
- Retrieves relevant evidence from the supplied product knowledge base.
- Uses structured Gemini generation when an API key is configured.
- Validates generated output using Pydantic schemas.
- Verifies that known-issue citations exist in the retrieved evidence.
- Falls back to deterministic triage when an external LLM is unavailable.
- Produces a structured triage result containing:
  - Product area
  - Category
  - Urgency
  - Decision rationale
  - Known issue detection
  - Responder team
  - Draft customer response

Historical ticket labels are intentionally **not used as Task 1 classification inputs**.

### Task 2 — TAM Account Health Brief

Given an account ID, the system generates a deterministic account brief by combining:

- Customer account information
- Recent ticket history
- Dataset-relative 90-day activity
- Account health
- Usage trends
- License utilization
- Renewal timing
- P1 incidents
- Open support issues
- Escalation notes
- Customer satisfaction signals
- Churn and escalation indicators

The account analysis is deterministic so that the same dataset and input produce reproducible results.

---

# Key Capabilities

- Knowledge-base-grounded ticket triage
- Local TF-IDF retrieval over the supplied documentation
- Optional Gemini-powered structured generation
- Deterministic offline fallback
- Pydantic schema validation
- Knowledge-base citation validation
- Input validation and normalization
- Sensitive-data redaction before external LLM calls
- Deterministic TAM account health analysis
- Dataset-relative time windows for reproducibility
- Command-line interface
- REST API
- Automated testing
- Evaluation harness with adversarial cases
- GitHub Actions CI
- Versioned prompts for controlled prompt iteration

---

# Architecture

## Task 1 — Ticket Triage

```text
Raw Ticket Input
(Text / Subject + Body / Ticket ID)
        |
        v
Input Validation & Normalization
        |
        v
Knowledge Base Retrieval
(Local TF-IDF)
        |
        v
Retrieved Evidence
        |
        +-----------------------------+
        |                             |
        v                             v
Structured LLM Generation      Deterministic Fallback
(Optional Gemini)
        |                             |
        +--------------+--------------+
                       |
                       v
              Pydantic Validation
                       |
                       v
        Knowledge Base Citation Check
                       |
                       v
                 TriageResult
```

### Data Flow

1. Raw ticket content is validated and normalized.
2. Relevant knowledge-base sections are retrieved locally.
3. When Gemini is configured, the ticket and retrieved evidence are sent to the model.
4. The model is constrained to return structured JSON.
5. The response is validated against the `TriageResult` schema.
6. Any known-issue citation must match a document and section present in the retrieved evidence.
7. If the LLM is unavailable or not configured, deterministic fallback logic produces a valid result.

---

## Task 2 — TAM Account Health

```text
Account ID
    |
    +-------> accounts.json
    |
    +-------> tickets.json
                  |
                  v
       Dataset-relative 90-Day Window
                  |
                  v
        Deterministic Risk Signals
                  |
                  +-----------------------+
                  |                       |
                  v                       v
          Account Health            Ticket Signals
          Usage & Renewal           Escalations
          CSAT / NPS                P1 Incidents
          Open Tickets              Churn Indicators
                  |
                  v
              AccountBrief
```

The default reference date is derived from the latest supplied ticket timestamp, ensuring that the analysis remains reproducible regardless of when the evaluator runs the repository.

---

# Project Structure

```text
.
├── .github/
│   └── workflows/
│       └── eval.yml
│
├── data/
│   ├── accounts.json
│   └── tickets.json
│
├── docs/
│   └── design-note.md
│
├── knowledge-base/
│   ├── billing/
│   ├── onboarding/
│   ├── products/
│   └── troubleshooting/
│
├── prompts/
│   ├── README.md
│   └── triage_v1.md
│
├── scripts/
│   └── run_eval.py
│
├── src/
│   └── support_ai/
│       ├── api.py
│       ├── cli.py
│       ├── config.py
│       ├── data.py
│       ├── eval.py
│       ├── health.py
│       ├── llm.py
│       ├── models.py
│       ├── retrieval.py
│       ├── triage.py
│       └── prompts/
│
├── tests/
│
├── DATA_SCHEMA.md
├── README.md
├── requirements.txt
├── pyproject.toml
└── .env.example
```

---

# Technology Stack

| Area | Technology |
|---|---|
| Language | Python 3.11+ |
| API | FastAPI |
| Validation | Pydantic |
| LLM | Google Gemini (optional) |
| Retrieval | Local TF-IDF |
| Testing | Pytest |
| CI | GitHub Actions |
| Configuration | Environment Variables |
| Packaging | Python package with CLI entry point |

The dependency footprint is intentionally kept small. A vector database or agent framework would add unnecessary complexity for a knowledge base of this size.

---

# Setup

## Requirements

- Python 3.11 or newer
- pip
- Optional: Gemini API key for live LLM-powered triage

## Create a Virtual Environment

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

# Configuration

Copy the environment template.

### Windows

```bash
copy .env.example .env
```

### macOS / Linux

```bash
cp .env.example .env
```

Configure the environment variables:

```env
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | No | Enables live Gemini-powered ticket triage |
| `GEMINI_MODEL` | No | Gemini model name |
| `SUPPORT_AI_AS_OF` | No | ISO-8601 reference timestamp for reproducible account analysis |

If `GEMINI_API_KEY` is not configured, Task 1 continues to work using deterministic fallback logic.

No API credentials should be committed to source control.

---

# Usage

## Ticket Triage

### Triage a Supplied Ticket

```bash
support-ai triage --ticket-id TKT-10050
```

### Triage Raw Text

```bash
support-ai triage --text "We have a critical outage affecting all users."
```

### Triage Structured Input

```bash
support-ai triage --json "{\"subject\":\"How do I configure SSO?\",\"body\":\"Please help.\"}"
```

---

## TAM Account Health Brief

```bash
support-ai account ACC-7397
```

The account pipeline:

1. Loads the account.
2. Joins relevant ticket history.
3. Applies the dataset-relative 90-day window.
4. Computes deterministic health and risk signals.
5. Produces an actionable account brief.

---

# Evaluation

Run the complete test suite:

```bash
pytest -q
```

Run the evaluation harness:

```bash
python scripts/run_eval.py
```

The evaluation report is written to:

```text
eval_report.json
```

The project also supports:

```bash
support-ai eval
```

The evaluation includes:

- Normal cases
- Knowledge-base-grounded cases
- Urgency classification
- Adversarial input
- Deterministic fallback behavior
- Account risk analysis
- 90-day ticket windows
- Escalation signals
- Renewal risk
- Missing and no-ticket scenarios

Each evaluation produces:

- Per-case results
- Pass/fail checks
- Quality scores from `0` to `1`
- Aggregate task scores
- Overall evaluation score

---

# REST API

Start the API server:

```bash
uvicorn support_ai.api:app --host 0.0.0.0 --port 8000
```

## Endpoints

### Health Check

```text
GET /health
```

### Ticket Triage

```text
POST /triage
```

Example:

```json
{
  "text": "Our production users cannot access the application."
}
```

Or:

```json
{
  "subject": "Production outage",
  "body": "All users are unable to access the application."
}
```

### Account Health Brief

```text
GET /accounts/{account_id}/brief
```

Example:

```text
GET /accounts/ACC-7397/brief
```

The API validates request structure and rejects unsupported fields.

---

# Knowledge Base Retrieval

The retrieval corpus consists exclusively of the supplied:

```text
knowledge-base/
```

documents.

Documents preserve:

- Document path
- Section metadata
- Evidence text

The current implementation uses TF-IDF retrieval because the supplied knowledge base is small and does not justify vector-database infrastructure.

The retrieval layer is isolated behind a dedicated module, allowing future upgrades such as:

- Embedding-based retrieval
- Hybrid retrieval
- Cross-encoder reranking
- Semantic search
- Persistent indexes

without requiring major changes to the core application architecture.

---

# LLM Reliability & Validation

The Gemini integration is designed defensively and includes:

- Structured JSON responses
- Pydantic schema validation
- Deterministic generation settings
- Request timeout
- Retry handling
- Empty-response detection
- Invalid-output detection
- Knowledge-base citation validation
- Deterministic fallback

A generated known issue cannot cite arbitrary knowledge-base content.

If the model claims that a known issue was found, the cited:

```text
document + section
```

must exist in the retrieved evidence.

Unsupported citations are rejected rather than silently returned.

---

# Security & Privacy

The project follows production-oriented security practices appropriate for the assessment.

- API credentials are loaded from environment variables.
- `.env` files are excluded from Git.
- `.env.example` contains placeholders only.
- Customer text is treated as untrusted input.
- Embedded instructions inside ticket content are not treated as system instructions.
- Common identifiers are redacted before data crosses the external LLM boundary.
- Common email addresses and phone numbers are redacted.
- Secret-like values are redacted.
- Input size and structure are validated by the API.

The redaction implementation covers common patterns and is not a replacement for enterprise-grade DLP tooling.

---

# Testing Strategy

Run all tests:

```bash
pytest -q
```

The test suite covers important behavior including:

- Input validation
- Ticket loading
- Account loading
- Knowledge-base retrieval
- Triage logic
- Known issue matching
- API request handling
- LLM output validation
- Deterministic fallback behavior
- Account health analysis
- Evaluation requirements

Tests focus on validating observable behavior and important failure paths rather than simply maximizing coverage.

---

# Engineering Decisions

## 1. Retrieval Before Generation

Knowledge-base evidence is retrieved before LLM generation.

This reduces hallucination risk and provides relevant product context for classification and response generation.

## 2. Local TF-IDF Instead of a Vector Database

The supplied knowledge base contains a small number of documents.

Introducing a vector database would increase:

- Operational complexity
- Dependencies
- Infrastructure requirements

without providing proportional value at this scale.

A local TF-IDF index is simpler, reproducible, and sufficient for the supplied dataset.

## 3. LLMs Only Where They Add Value

Task 1 benefits from contextual reasoning for:

- Classification
- Routing
- Evidence interpretation
- Response drafting

Task 2 is deterministic because account-health analysis benefits from:

- Reproducibility
- Explainability
- Consistent risk signals

## 4. Historical Labels Are Not Treated as Ground Truth

Historical ticket fields such as:

- Category
- Urgency
- Product area

are excluded from Task 1 classification inputs.

The system evaluates raw ticket content independently.

## 5. Dataset-Relative Time

The account-health pipeline uses the supplied dataset as its temporal reference.

By default, the latest supplied ticket timestamp becomes the reference point for the 90-day analysis window.

This avoids results changing simply because the evaluator runs the project on a different date.

## 6. Fail Closed on Unsupported Evidence

Generated known-issue citations are validated against retrieved evidence.

Unsupported citations are rejected rather than silently returned.

---

# Production Considerations

The current implementation is intentionally lightweight but designed to evolve.

A larger production deployment could add:

- Persistent retrieval indexes
- Embedding-based retrieval
- Reranking
- Centralized logging
- Metrics and alerting
- Distributed tracing
- Rate limiting
- Authentication and authorization
- Background processing
- Provider fallback
- Enterprise DLP integration
- Evaluation dashboards
- Model monitoring

The architecture keeps these future concerns separate from the core business logic.

---

# Limitations

- TF-IDF retrieval is lexical and may miss semantically equivalent language.
- Gemini availability and quota affect live LLM triage.
- The deterministic fallback is intentionally less expressive than the LLM path.
- PII redaction covers common patterns rather than every possible sensitive-data format.
- The TAM summarizer is deterministic and template-driven.
- Production authentication and rate limiting are not included.
- Observability is intentionally lightweight for this assessment implementation.

---

# Design Documentation

Detailed architecture and production considerations are available in:

```text
docs/design-note.md
```

The design note covers:

- Failure modes
- Latency and quality trade-offs
- Data sensitivity
- Scaling considerations
- Reliability decisions

---

# Continuous Integration

GitHub Actions runs the evaluation workflow on:

- Pushes
- Pull requests

This provides automated regression detection for the project's evaluation suite.

---

# Design Principles

The implementation prioritizes:

```text
Correctness
    ↓
Reproducibility
    ↓
Maintainability
    ↓
Evidence-Grounded AI Behavior
    ↓
Simple Architecture
    ↓
Production Extensibility
```

The objective is not to add unnecessary AI infrastructure, but to build the simplest system that reliably satisfies the requirements while remaining straightforward to maintain and extend.

---

