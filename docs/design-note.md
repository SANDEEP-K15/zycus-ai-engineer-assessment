# Design Note

## Failure modes

**1. Retrieval misses the correct knowledge-base guidance.** The local TF-IDF retriever can miss semantically equivalent wording or rank a generic section above a precise error-code entry. Detection comes from retrieval/evaluation cases and the requirement that any generated known-issue citation must reference a retrieved document/section. Mitigation: add embedding retrieval and a lightweight reranker behind the existing retrieval interface, then monitor top-k recall on a curated support set.

**2. LLM output is malformed, unsafe, or overconfident.** Gemini output is constrained to JSON, validated with Pydantic, and checked so any `known_issue` citation must belong to the retrieved evidence. The client uses a timeout and one retry. Ticket text is explicitly treated as untrusted data, and common identifiers/secrets are redacted before the external call. Production monitoring should track schema failures, retries, unsupported-citation attempts, fallback rates, latency, and unsupported-claim evaluations.

**3. Customer data crosses an external model boundary.** Tickets may contain PII or commercially sensitive information. The implementation performs local pattern-based redaction before Gemini receives the prompt and never commits credentials. A production deployment should replace the lightweight redactor with enterprise DLP, minimize retained prompt data, enforce provider retention controls, and audit access to the model boundary.

## Latency vs quality

I chose a local TF-IDF retrieval layer instead of a hosted vector database or embedding service. With nine supplied documents, this keeps retrieval fast, reproducible, cheap, and within the supplied-data constraint. The trade-off is weaker semantic recall. If latency were the hard constraint, I would keep the local index, cache repeated retrieval queries, reduce context to the strongest evidence, and route straightforward tickets to the deterministic path while reserving LLM calls for ambiguous cases.

## Data sensitivity

Only the synthetic assessment dataset is used. No scraping or external customer data is introduced. The LLM boundary is isolated in `llm.py`, and common account/ticket IDs, email addresses, phone numbers, and secret-like values are redacted before the provider call. The remaining limitation is that regex redaction is not a complete DLP system; production should use an enterprise-approved redaction policy and provider retention controls.

## Scaling

At 10× ticket volume, the local JSON load remains manageable for this assessment, but repeated full scans become the first avoidable cost. The next bottleneck is LLM inference and provider rate limits. For production, I would index tickets by account and creation time, persist the retrieval index, cache repeated KB searches, batch offline evaluations, and add concurrency/rate-limit controls. The API layer is stateless, so it can scale horizontally once authentication, observability, and persistent indexing are added.

## Operational safeguards

The core services are intentionally stateless: the KB index is rebuilt from the supplied Markdown corpus at process startup, while account and ticket data are read from the repository. This is appropriate for the assessment size and keeps behavior reproducible. In production, I would move immutable reference data to managed storage, pre-build the retrieval index during deployment, and version the index alongside the prompt and model configuration. For every triage request, metrics should record retrieval latency, top-k confidence, model latency, schema-validation failures, retry count, fallback usage, and a privacy-safe request identifier. Logs must exclude raw ticket bodies and model prompts. Access to account-health endpoints should also be authenticated and authorized because ARR, renewal dates, NPS, and escalation notes are commercially sensitive.

The evaluation harness is deliberately separated from the runtime path. It uses deterministic acceptance criteria instead of pretending that a single aggregate score proves production quality. A real deployment should add a versioned gold set, periodic human review, retrieval recall measurements, and a small LLM-as-judge component only where semantic quality cannot be expressed with deterministic checks. Regression gates should fail CI when quality drops below an agreed threshold, not merely when a Python test fails.
