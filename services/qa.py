"""Freeform Q&A over stored people/facts/notes using Claude."""
from config import Config
from services.claude_client import complete

SYSTEM = (
    "You are a personal memory assistant. Answer the user's question using ONLY the "
    "stored information provided below. Be direct and conversational (1-3 sentences "
    "unless more is genuinely needed). If the answer is not in the stored information, "
    "say you don't have that noted yet - do not guess. If it's unclear which person "
    "the question is about, ask a brief clarifying question."
)


def _format_person_block(person, facts, notes=None):
    lines = [f"### {person['name']} ({person['relationship_type']})"]
    if person.get("context"):
        lines.append(f"Context: {person['context']}")
    if facts:
        for f in facts:
            lines.append(f"- {f['key']}: {f['value']}")
    else:
        lines.append("- (no facts yet)")
    if notes:
        lines.append("Recent notes:")
        for n in notes:
            date = (n.get("created_at") or "")[:10]
            lines.append(f"  - [{date}] {n['raw_text']}")
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
        f"## Question\n{question}\n\nAnswer using only the stored information above."
    )
    return complete(SYSTEM, user, model=Config.CLAUDE_MODEL_FAST,
                    max_tokens=350, temperature=0.2)
