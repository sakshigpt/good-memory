from flask import Blueprint, jsonify, request

import database as db

people_bp = Blueprint("people", __name__)


@people_bp.route("/api/people", methods=["GET"])
def list_people():
    return jsonify(db.list_people())


@people_bp.route("/api/people", methods=["POST"])
def create_person():
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    rel = (data.get("relationship_type") or "friend").strip()
    context = (data.get("context") or "").strip()
    return jsonify(db.create_person(name, rel, context)), 201


@people_bp.route("/api/people/<int:person_id>", methods=["GET"])
def get_person(person_id):
    person = db.get_person(person_id)
    if not person:
        return jsonify({"error": "not found"}), 404
    person["facts"] = db.get_active_facts(person_id)
    person["recent_notes"] = db.list_notes(person_id, limit=10)
    person["pending_conflicts"] = db.list_conflicts(person_id, status="pending")
    return jsonify(person)


@people_bp.route("/api/people/<int:person_id>", methods=["PUT"])
def update_person(person_id):
    if not db.get_person(person_id):
        return jsonify({"error": "not found"}), 404
    data = request.get_json(force=True) or {}
    return jsonify(db.update_person(
        person_id,
        name=data.get("name"),
        relationship_type=data.get("relationship_type"),
        context=data.get("context"),
    ))


@people_bp.route("/api/people/<int:person_id>", methods=["DELETE"])
def delete_person(person_id):
    db.delete_person(person_id)
    return jsonify({"ok": True})
