"""Shared Anthropic client + helper to call Claude and get plain text back."""
import anthropic

from config import Config

_client = None


def get_client():
    global _client
    if _client is None:
        Config.require_anthropic()
        _client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
    return _client


def complete(system, user, model=None, max_tokens=600, temperature=0.2):
    """Single-turn completion. Returns the text of the first content block."""
    client = get_client()
    resp = client.messages.create(
        model=model or Config.CLAUDE_MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    return "".join(parts).strip()
