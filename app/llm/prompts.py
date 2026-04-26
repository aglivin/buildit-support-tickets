SYSTEM_PROMPT = """You are a support ticket triage classifier for a B2B SaaS company.
Classify the support ticket using the record_triage tool.
Be precise and conservative: base your classification only on what is written in the ticket."""

TRIAGE_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "record_triage",
        "description": "Record the structured triage classification for a support ticket.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["billing", "bug", "feature_request", "account", "other"],
                    "description": (
                        "billing: charges, refunds, invoices, subscription. "
                        "bug: crashes, errors, freezes, unexpected behavior. "
                        "feature_request: suggestions, improvements, 'would be nice'. "
                        "account: login, password, access, permissions. "
                        "other: anything that does not clearly fit the above."
                    ),
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "description": (
                        "urgent: user completely blocked from working, or there is data loss / payment issue. "
                        "high: core feature broken but a workaround exists. "
                        "medium: significant inconvenience, not blocking. "
                        "low: minor issue, question, or positive feedback."
                    ),
                },
                "sentiment": {
                    "type": "string",
                    "enum": ["negative", "neutral", "positive"],
                    "description": (
                        "The emotional tone expressed by the customer's writing style, "
                        "not the severity of their situation. "
                        "negative: angry, frustrated, upset, or complaint language. "
                        "neutral: factual, calm, or matter-of-fact tone with no strong emotion. "
                        "positive: appreciative, happy, or enthusiastic language."
                    ),
                },
                "summary": {
                    "type": "string",
                    "description": "One English sentence summarising the issue. Maximum 20 words. No PII.",
                },
            },
            "required": ["category", "priority", "sentiment", "summary"],
        },
    },
}
