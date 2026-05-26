"""Freeform Q&A over stored people/facts/notes using Claude."""
from config import Config
from services.claude_client import complete

SYSTEM = (
    "You are a personal memory assistant. The user wants to recall something about "
    "someone they know. You have two sources of information about each person:\n\n"
    "  NOTES — raw text the user wrote after conversations. These are the PRIMARY "
    "source. They contain stories, opinions, impressions, qualitative assessments, "
    "and context that may never appear in structured facts.\n\n"
    "  FACTS — structured key/value pairs extracted from the notes. Useful for "
    "quick lookups (birthday, employer, pet name etc.) but incomplete for "
    "qualitative or descriptive questions.\n\n"
    "When answering:\n"
    "- For qualitative questions ('how is X?', 'what's X like?', 'would you "
    "  recommend X?') — search the NOTES section carefully. The answer is almost "
    "  always there even if it wasn't captured in structured facts.\n"
    "- For factual lookups ('what is X's job?', 'what's the dog's name?') — the "
    "  FACTS section may answer it directly.\n"
    "- Always prefer a specific, grounded answer drawn from the stored material.\n"
    "- Be direct and conversational (1–3 sentences unless more detail is helpful).\n"
    "- If the answer genuinely isn't in either source, say so honestly — do not invent."
)


def _format_person_block(person, facts, notes=None):
    lines = [f"### {person['name']} ({person['relationship_type']})"]
    if person.get("context"):
        lines.append(f"Context: {person['context']}")

    # Notes come FIRST — they are richer and more qualitative than structured facts.
    if notes:
        lines.append("\nNOTES (primary source — read these carefully):")
        for n in notes:
            date = (n.get("created_at") or "")[:10]
            lines.append(f"  [{date}] {n['raw_text']}")

    lines.append("\nEXTRACTED FACTS (structured index — may be incomplete):")
    if facts:
        for f in facts:
            lines.append(f"  - {f['key']}: {f['value']}")
    else:
        lines.append("  (none extracted yet — see notes above)")

    return "\n".join(lines)


def answer_question(question, people_context):
    """people_context: list of {person, facts, notes?} dicts."""
    if not people_context:
        blocks = "(no people stored yet)"
    else:
        blocks = "\n\n".join(
            _format_person_block(pc["person"], pc.get("facts", []), pc.get("notes"))
            for pc in people_context
        )
    user = (
        f"## Stored information\n{blocks}\n\n"
        f"## Question\n{question}\n\n"
        "Answer using the stored information above. Check the NOTES section "
        "carefully before concluding something isn't known."
    )
    return complete(SYSTEM, user, model=Config.CLAUDE_MODEL_FAST,
                    max_tokens=400, temperature=0.2)
