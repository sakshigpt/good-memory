"""Extract structured facts from a raw conversation note using Claude."""
import json
import re

from config import Config
from services.claude_client import complete

CATEGORIES = [
    "employer", "family", "pets", "personal", "health",
    "hobbies", "location", "preferences", "assessments", "other",
]

SYSTEM = (
    "You are a personal memory assistant. Extract durable details about a person from "
    "a conversation note. Return ONLY a JSON array (no prose, no markdown fences). "
    "Each element is an object with exactly these keys:\n"
    '  - "category": one of ' + ", ".join(CATEGORIES) + "\n"
    '  - "key": a short snake_case slot id, stable across notes '
    '(e.g. "employer_name", "job_title", "dog_name", "birthday", "spouse_name", '
    '"home_city", "favorite_food", "overall_quality", "recommendation", '
    '"personality_trait", "pricing", "availability"). Reuse the same key for the '
    "same kind of fact.\n"
    '  - "value": the value as a concise string.\n\n'
    "Rules:\n"
    "- Extract clearly stated facts AND qualitative assessments / impressions.\n"
    "  The 'assessments' category is for quality ratings, personality traits, "
    "  standout attributes, and recommendations — e.g. overall_quality, "
    "  recommendation, key_strength, pricing, availability, personality_trait.\n"
    "- For service providers (drivers, contractors, vendors etc.) always capture "
    "  quality signals: reliability, pricing, standout strengths, recommendation.\n"
    "- Dates: use YYYY-MM-DD if fully known, else a partial like 'March 15' or '1990'.\n"
    "- Family members: keys like 'mother_name', 'brother_name', 'son_name'.\n"
    "- Multiple of a kind: suffix with _1, _2 (e.g. 'dog_name_1', 'dog_name_2').\n"
    "- Do NOT extract the person's own name or relationship (already known).\n"
    "- Skip empty small talk with no lasting value.\n"
    "- If nothing worth storing is present, return []."
)


def _parse_json_array(text):
    text = text.strip()
    # Strip ```json ... ``` fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # Grab the outermost [ ... ] if there is extra prose
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]
    data = json.loads(text)
    if not isinstance(data, list):
        return []
    clean = []
    for item in data:
        if not isinstance(item, dict):
            continue
        cat = str(item.get("category", "other")).strip().lower()
        key = str(item.get("key", "")).strip()
        val = str(item.get("value", "")).strip()
        if not key or not val:
            continue
        if cat not in CATEGORIES:
            cat = "other"
        clean.append({"category": cat, "key": key, "value": val})
    return clean


def _format_existing(existing_facts):
    """Render existing facts so the model reuses the same keys (critical for
    conflict detection, which matches on key)."""
    if not existing_facts:
        return ""
    lines = [f"- {f['key']} (currently: {f['value']})" for f in existing_facts]
    return (
        "\n\nThis person already has these fact keys on file. If the note mentions "
        "the SAME kind of fact, REUSE the exact same key (even if the value differs "
        "— a differing value is expected and handled elsewhere). Only invent a new "
        "key for a genuinely new kind of fact:\n" + "\n".join(lines)
    )


def extract_facts(person_name, relationship, raw_note, existing_facts=None):
    """Returns a list of {category, key, value} dicts. Empty list on failure.

    existing_facts: optional list of the person's current {key, value} facts, so
    the model reuses established keys (makes conflict detection reliable)."""
    user = (
        f"Person: {person_name} ({relationship})\n"
        f"Conversation note:\n\"\"\"\n{raw_note}\n\"\"\"\n"
        f"{_format_existing(existing_facts)}\n\n"
        "Extract the facts as a JSON array now."
    )
    raw = complete(SYSTEM, user, model=Config.CLAUDE_MODEL_FAST,
                   max_tokens=800, temperature=0.0)
    try:
        return _parse_json_array(raw)
    except Exception:
        # one retry with a stricter nudge
        retry = complete(
            SYSTEM,
            user + "\n\nYour previous reply was not valid JSON. "
                   "Respond with ONLY a valid JSON array.",
            model=Config.CLAUDE_MODEL_FAST, max_tokens=800, temperature=0.0)
        try:
            return _parse_json_array(retry)
        except Exception:
            return []
