"""Configuration loaded from environment / .env file."""
import os
from dotenv import load_dotenv

# Load .env from the project root (directory containing this file).
# override=True so values in .env win over empty/stale shell env vars
# (e.g. an exported ANTHROPIC_API_KEY="" in the user's shell profile).
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
            override=True)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _abs(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(_BASE_DIR, path)


class Config:
    # --- AI ---
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    CLAUDE_MODEL_FAST = os.environ.get("CLAUDE_MODEL_FAST", "claude-haiku-4-5-20251001")

    # --- Voice transcription ---
    WHISPER_BACKEND = os.environ.get("WHISPER_BACKEND", "local")  # "local" | "groq"
    WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")       # tiny | base | small
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

    # --- Storage / server ---
    DB_PATH = _abs(os.environ.get("DB_PATH", "data/good_memory.db"))
    FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    PORT = int(os.environ.get("PORT", "5000"))

    @classmethod
    def require_anthropic(cls):
        if not cls.ANTHROPIC_API_KEY:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to good-memory/.env"
            )
