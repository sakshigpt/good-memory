from flask import Blueprint, jsonify, request

import database as db

facts_bp = Blueprint("facts", __name__)


@facts_bp.route("/api/people/<int:person_id>/facts", methods=["GET"])
def list_facts(person_id):
    return jsonify(db.get_active_facts(person_id))


@facts_bp.route("/api/facts/<int:fact_id>", methods=["PUT"])
def update_fact(fact_id):
    if not db.get_fact(fact_id):
        return jsonify({"error": "not found"}), 404
    data = request.get_json(force=True) or {}
    value = (data.get("value") or "").strip()
    if not value:
        return jsonify({"error": "value is required"}), 400
    db.update_fact_value(fact_id, value)
    return jsonify(db.get_fact(fact_id))


@facts_bp.route("/api/facts/<int:fact_id>", methods=["DELETE"])
def delete_fact(fact_id):
    db.deactivate_fact(fact_id)
    return jsonify({"ok": True})
