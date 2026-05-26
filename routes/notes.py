from flask import Blueprint, jsonify, request

import database as db
from services import extraction
from services import conflict as conflict_service

notes_bp = Blueprint("notes", __name__)


@notes_bp.route("/api/people/<int:person_id>/notes", methods=["GET"])
def list_notes(person_id):
    return jsonify(db.list_notes(person_id))


@notes_bp.route("/api/people/<int:person_id>/notes", methods=["POST"])
def create_note(person_id):
    person = db.get_person(person_id)
    if not person:
        return jsonify({"error": "person not found"}), 404

    data = request.get_json(force=True) or {}
    raw_text = (data.get("raw_text") or "").strip()
    if not raw_text:
        return jsonify({"error": "raw_text is required"}), 400
    source = data.get("source", "text")

    # 1. Persist the raw note first (never lose the user's words).
    note_id = db.insert_note(person_id, raw_text, source)

    # 2. Extract facts via Claude, passing existing facts so it reuses keys
    #    (so conflict detection, which matches on key, works reliably).
    try:
        existing_facts = db.get_active_facts(person_id)
        extracted = extraction.extract_facts(
            person["name"], person["relationship_type"], raw_text,
            existing_facts=existing_facts)
        extraction_error = None
    except Exception as e:
        extracted, extraction_error = [], str(e)

    inserted_facts, new_conflicts = [], []

    # 3. For each fact, insert or flag a conflict.
    for fact in extracted:
        conflict = conflict_service.detect_conflict(
            person_id, fact["key"], fact["value"])
        if conflict is None:
            existing = db.get_active_fact_by_key(person_id, fact["key"])
            if existing:
                continue  # identical value already stored; skip duplicate
            fact_id = db.insert_fact(
                person_id, note_id, fact["category"], fact["key"], fact["value"])
            inserted_facts.append({**fact, "id": fact_id})
        else:
            conflict_id = db.insert_conflict(
                person_id, note_id, conflict["existing_fact_id"],
                fact["key"], fact["value"], fact["category"])
            new_conflicts.append({
                "conflict_id": conflict_id,
                "key": fact["key"],
                "category": fact["category"],
                "existing_value": conflict["existing_value"],
                "new_value": fact["value"],
            })

    return jsonify({
        "note_id": note_id,
        "extracted_facts": inserted_facts,
        "conflicts": new_conflicts,
        "extraction_error": extraction_error,
    }), 201


@notes_bp.route("/api/notes/<int:note_id>", methods=["DELETE"])
def delete_note(note_id):
    db.delete_note(note_id)
    return jsonify({"ok": True})
