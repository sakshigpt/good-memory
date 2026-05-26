"""Generate a warm, concise pre-call briefing using Claude."""
from config import Config
from services.claude_client import complete

SYSTEM = (
    "You are a thoughtful personal assistant preparing the user for a catch-up with "
    "someone they care about. Write a briefing that is warm and conversational, never "
    "clinical. Use the second person ('Priya is your...'). Keep it tight: 3-5 short "
    "bullet points, max ~180 words. Cover, as available: who this person is and how "
    "they fit in the user's life; the key personal details worth remembering (family, "
    "pets, work, location); anything recent or time-sensitive from the latest notes; "
    "and 1-2 natural conversation starters or things to follow up on. Only use the "
    "information provided. Do not invent details."
)


def _format_facts(facts):
    if not facts:
        return "(no structured facts yet)"
    by_cat = {}
    for f in facts:
        by_cat.setdefault(f["category"], []).append(f"{f['key']}: {f['value']}")
    lines = []
    for cat, items in by_cat.items():
        lines.append(f"- {cat}: " + "; ".join(items))
    return "\n".join(lines)


def _format_notes(notes):
    if not notes:
        return "(no notes logged yet)"
    lines = []
    for n in notes:
        date = (n.get("created_at") or "")[:10]
        lines.append(f"- [{date}] {n['raw_text']}")
    return "\n".join(lines)


def generate_briefing(person, facts, recent_notes, focus=""):
    user = (
        f"## Person\n"
        f"Name: {person['name']}\n"
        f"Relationship: {person['relationship_type']}\n"
        f"Context: {person.get('context') or '(none)'}\n\n"
        f"## Known facts\n{_format_facts(facts)}\n\n"
        f"## Recent notes (newest first)\n{_format_notes(recent_notes)}\n\n"
    )
    if focus:
        user += f"## Focus\nThe user specifically wants to focus on: {focus}\n\n"
    user += "Write the pre-call briefing now."
    return complete(SYSTEM, user, model=Config.CLAUDE_MODEL,
                    max_tokens=500, temperature=0.4)
