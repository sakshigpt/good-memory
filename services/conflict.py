"""Pure-Python conflict detection + resolution. No Claude calls."""
import database as db


def _normalize(s):
    return " ".join(str(s).strip().lower().split())


def detect_conflict(person_id, key, value):
    """Return {existing_fact_id, existing_value} if an active fact with the same key
    has a different value, else None."""
    existing = db.get_active_fact_by_key(person_id, key)
    if existing is None:
        return None
    if _normalize(existing["value"]) == _normalize(value):
        return None  # same value, no conflict
    return {"existing_fact_id": existing["id"], "existing_value": existing["value"]}


def resolve_conflict(conflict_id, resolution, merge_value=None, resolution_note=""):
    """resolution: 'new' | 'old' | 'merge'. Returns the resulting active fact (or None)."""
    conflict = db.get_conflict(conflict_id)
    if conflict is None:
        raise ValueError("Conflict not found")
    if conflict["status"] != "pending":
        raise ValueError("Conflict already resolved")

    existing_fact = db.get_fact(conflict["existing_fact_id"])
    result_fact = None

    if resolution == "old":
        # Keep existing fact; discard the new value.
        db.mark_conflict_resolved(conflict_id, "resolved_old", resolution_note)
        result_fact = existing_fact

    elif resolution == "new":
        if existing_fact:
            db.deactivate_fact(existing_fact["id"])
        new_id = db.insert_fact(
            conflict["person_id"], conflict["note_id"],
            conflict["category"], conflict["new_key"], conflict["new_value"])
        db.mark_conflict_resolved(conflict_id, "resolved_new", resolution_note)
        result_fact = db.get_fact(new_id)

    elif resolution == "merge":
        if not merge_value:
            raise ValueError("merge_value is required for a merge resolution")
        if existing_fact:
            db.deactivate_fact(existing_fact["id"])
        new_id = db.insert_fact(
            conflict["person_id"], conflict["note_id"],
            conflict["category"], conflict["new_key"], merge_value)
        db.mark_conflict_resolved(conflict_id, "resolved_merge", resolution_note)
        result_fact = db.get_fact(new_id)

    else:
        raise ValueError("resolution must be one of: new, old, merge")

    return result_fact
