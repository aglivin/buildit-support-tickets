from openai import AsyncOpenAI

from app.config import settings

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client  # pylint: disable=global-statement  # module-level singleton; only mutated here
    if _client is None:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client
