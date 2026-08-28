# Prompt Versioning

## triage-v1

The canonical Task 1 prompt is `prompts/triage_v1.md`. Runtime code loads this versioned file before each Gemini triage call.

### Changelog

- `triage-v1`: initial production-oriented prompt with KB-only grounding, structured JSON output, untrusted-ticket handling, evidence requirements, and no-invention rules.
