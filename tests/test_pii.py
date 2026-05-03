"""PII masking: unit tests for app/services/pii.py."""

from app.services.pii import mask_for_llm

# ── Email masking ─────────────────────────────────────────────────────────────


def test_email_local_part_is_masked():
    result = mask_for_llm("Contact me at anna@example.com please")
    assert "anna" not in result
    assert "[EMAIL_1]@example.com" in result


def test_email_domain_is_preserved():
    result = mask_for_llm("From enterprise@bigcorp.io")
    assert "bigcorp.io" in result


def test_multiple_emails_get_sequential_tokens():
    result = mask_for_llm("Send to a@x.com and b@y.com")
    assert "[EMAIL_1]@x.com" in result
    assert "[EMAIL_2]@y.com" in result


# ── API key masking ───────────────────────────────────────────────────────────


def test_anthropic_key_is_redacted():
    text = "My key is sk-ant-api03-AAAAAAAAAAAAAAAA and it stopped working"
    result = mask_for_llm(text)
    assert "sk-ant-api03" not in result
    assert "[REDACTED_KEY]" in result


def test_openai_style_key_is_redacted():
    text = "Here is my key: sk-aBcDeFgHiJkLmNoPqRsTuVwXyZ123456"
    result = mask_for_llm(text)
    assert "sk-" not in result
    assert "[REDACTED_KEY]" in result


def test_aws_access_key_is_redacted():
    text = "AWS key: AKIAIOSFODNN7EXAMPLE used in prod"
    result = mask_for_llm(text)
    assert "AKIAIOSFODNN7EXAMPLE" not in result
    assert "[REDACTED_KEY]" in result


# ── Phone masking ─────────────────────────────────────────────────────────────


def test_us_phone_is_masked():
    result = mask_for_llm("Call me at 555-867-5309 anytime")
    assert "555-867-5309" not in result
    assert "[PHONE_1]" in result


def test_international_phone_is_masked():
    result = mask_for_llm("Reach me at +44 7911 123456")
    assert "+44 7911 123456" not in result
    assert "[PHONE_1]" in result


# ── IBAN masking ──────────────────────────────────────────────────────────────


def test_iban_is_redacted():
    result = mask_for_llm("Please refund to GB29NWBK60161331926819")
    assert "GB29NWBK60161331926819" not in result
    assert "[REDACTED_IBAN]" in result


# ── Clean text is unchanged ───────────────────────────────────────────────────


def test_plain_text_is_unchanged():
    text = "The app crashes when I export to PDF on macOS 14."
    assert mask_for_llm(text) == text
