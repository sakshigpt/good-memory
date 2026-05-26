from flask import Blueprint, jsonify, request

import database as db
from services import conflict as conflict_service

conflicts_bp = Blueprint("conflicts", __name__)


@conflicts_bp.route("/api/conflicts", methods=["GET"])
def list_all_conflicts():
    return jsonify({
        "conflicts": db.list_conflicts(status="pending"),
        "count": db.count_pending_conflicts(),
    })


@conflicts_bp.route("/api/people/<int:person_id>/conflicts", methods=["GET"])
def list_person_conflicts(person_id):
    return jsonify(db.list_conflicts(person_id, status="pending"))


@conflicts_bp.route("/api/conflicts/<int:conflict_id>/resolve", methods=["POST"])
def resolve(conflict_id):
    data = request.get_json(force=True) or {}
    resolution = data.get("resolution")
    if resolution not in ("new", "old", "merge"):
        return jsonify({"error": "resolution must be new, old, or merge"}), 400
    try:
        fact = conflict_service.resolve_conflict(
            conflict_id,
            resolution,
            merge_value=(data.get("merge_value") or "").strip() or None,
            resolution_note=(data.get("resolution_note") or "").strip(),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "fact": fact})
