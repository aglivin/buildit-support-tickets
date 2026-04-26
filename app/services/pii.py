import re

# API keys before email — avoids mangling keys that contain @-like substrings
_API_KEY_RE = re.compile(
    r"sk-ant-api[\w\-]{10,}"  # Anthropic
    r"|sk-[\w\-]{20,}"  # OpenAI-style
    r"|pk_(?:live|test)_[\w\-]{10,}"  # Stripe
    r"|AKIA[A-Z0-9]{16}"  # AWS access key ID
    r"|[A-Za-z0-9+/]{40,}={0,2}",  # long base64 blobs (potential secrets)
)
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}[A-Z0-9]{0,16}\b")
# Credit-card-like sequences of 13–19 digits (with optional separators)
_CARD_RE = re.compile(r"\b(?:\d[ \-]?){12}\d{1,7}\b")
# Email: keep domain as a useful signal for the LLM, mask only local part
_EMAIL_RE = re.compile(r"([A-Za-z0-9._%+\-]+)@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})")
_PHONE_RE = re.compile(
    r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"  # US/CA
    r"|\+\d{1,3}[\s\-]?\(?\d{1,4}\)?[\s\-]?\d{1,4}[\s\-]?\d{1,9}",  # international
)


def mask_for_llm(text: str) -> str:
    counters: dict[str, int] = {}

    def _inc(key: str) -> int:
        counters[key] = counters.get(key, 0) + 1
        return counters[key]

    text = _API_KEY_RE.sub("[REDACTED_KEY]", text)
    text = _IBAN_RE.sub("[REDACTED_IBAN]", text)
    text = _CARD_RE.sub("[REDACTED_CARD]", text)
    text = _EMAIL_RE.sub(lambda m: f"[EMAIL_{_inc('e')}]@{m.group(2)}", text)
    text = _PHONE_RE.sub(lambda _: f"[PHONE_{_inc('p')}]", text)
    return text
