from support_ai.llm import _redact_sensitive


def test_redaction_removes_common_identifiers() -> None:
    value = {
        "body": "Contact jane@example.com, ticket TKT-10001, account ACC-1234, secret=abc123",
        "nested": ["+1 (555) 123-4567"],
    }
    redacted = _redact_sensitive(value)
    text = str(redacted)
    assert "jane@example.com" not in text
    assert "TKT-10001" not in text
    assert "ACC-1234" not in text
    assert "abc123" not in text
    assert "555" not in text
