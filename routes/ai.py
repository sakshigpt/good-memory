from flask import Blueprint, jsonify, request

import database as db
from services import briefing as briefing_service
from services import qa as qa_service

ai_bp = Blueprint("ai", __name__)


@ai_bp.route("/api/people/<int:person_id>/brief", methods=["POST"])
def brief(person_id):
    person = db.get_person(person_id)
    if not person:
        return jsonify({"error": "person not found"}), 404
    data = request.get_json(silent=True) or {}
    facts = db.get_active_facts(person_id)
    notes = db.list_notes(person_id, limit=5)
    try:
        text = briefing_service.generate_briefing(
            person, facts, notes, focus=(data.get("focus") or "").strip())
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"briefing": text})


@ai_bp.route("/api/qa", methods=["POST"])
def qa():
    data = request.get_json(force=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400

    person_id = data.get("person_id")
    if person_id:
        person = db.get_person(person_id)
        if not person:
            return jsonify({"error": "person not found"}), 404
        context = [{
            "person": person,
            "facts": db.get_active_facts(person_id),
            "notes": db.list_notes(person_id, limit=8),
        }]
    else:
        context = [
            {"person": {"name": p["name"],
                        "relationship_type": p["relationship_type"],
                        "context": p.get("context", "")},
             "facts": p["facts"]}
            for p in db.all_people_with_facts()
        ]

    try:
        answer = qa_service.answer_question(question, context)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"answer": answer})
