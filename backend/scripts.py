from __future__ import annotations

import json
from pathlib import Path
from typing import Any

if __package__:
    from .rules import normalize_rules, public_mode, validate_condition, validate_mode
else:
    from rules import normalize_rules, public_mode, validate_condition, validate_mode

SCRIPT_DIR = Path(__file__).with_name("scripts")
DEFAULT_SCRIPT_ID = "rain_lock"
PUBLIC_FIELDS = ("id", "title", "subtitle", "summary", "tags", "duration",
                 "difficulty", "theme", "locationLabel", "searchLimit")


def script_summary(script: dict[str, Any]) -> dict[str, Any]:
    return {**{key: script[key] for key in PUBLIC_FIELDS}, "playerCount": len(script["npcs"]),
            "availability": script["availability"], "source": script.get("source"),
            "mode": public_mode(script["mode"]), "coverText": script.get("coverText", script["title"][:2])}


def validate_script(script: dict[str, Any]) -> None:
    """Reject broken references at startup, before a player receives a book."""
    if not isinstance(script, dict):
        raise ValueError("Script must be a JSON object")
    normalize_rules(script)
    if "opening" in script and (not isinstance(script["opening"], str) or not script["opening"].strip()):
        raise ValueError("Invalid public opening")
    if script["schemaVersion"] != 2:
        raise ValueError("Unsupported script schemaVersion")
    availability = script["availability"]
    if (not isinstance(availability, dict) or availability.get("status") not in {"ready", "awaiting_materials"}
            or not isinstance(availability.get("note"), str)):
        raise ValueError("Invalid script availability")
    if script.get("theme") not in {"rain", "train", "manor", "western"}:
        raise ValueError("Unknown theme")
    if not isinstance(script.get("tags"), list) or any(not isinstance(tag, str) for tag in script["tags"]):
        raise ValueError("Invalid tags")
    if availability["status"] == "awaiting_materials":
        for key in PUBLIC_FIELDS:
            if key not in script:
                raise ValueError(f"Missing catalog field: {key}")
        for key in ("id", "title", "subtitle", "summary", "duration", "difficulty", "locationLabel"):
            if not isinstance(script[key], str) or not script[key].strip():
                raise ValueError(f"Invalid catalog field: {key}")
        roles = script.get("npcs")
        if not isinstance(roles, list) or len(roles) < 2:
            raise ValueError("Missing catalog roles")
        for role in roles:
            if any(not isinstance(role.get(key), str) or not role[key].strip()
                   for key in ("id", "name", "role", "public_profile", "initial_emotion")):
                raise ValueError("Invalid catalog role")
        role_ids = {role["id"] for role in roles}
        if len(role_ids) != len(roles):
            raise ValueError("Duplicate catalog roles")
        validate_mode(script["mode"], set(), role_ids)
        return
    for key in PUBLIC_FIELDS + ("victim", "killer", "truth", "publicEvidence",
                                "timeline", "evidence", "locations", "npcs"):
        if key not in script:
            raise ValueError(f"Missing script field: {key}")
    for key in ("id", "title", "subtitle", "summary", "duration", "difficulty",
                "locationLabel", "victim", "killer", "truth"):
        if not isinstance(script[key], str) or not script[key].strip():
            raise ValueError(f"Invalid script field: {key}")
    if script["theme"] not in {"rain", "train", "manor", "western"}:
        raise ValueError("Unknown theme")
    if not isinstance(script["tags"], list) or any(not isinstance(tag, str) for tag in script["tags"]):
        raise ValueError("Invalid tags")
    ids: dict[str, set[str]] = {}
    for key in ("npcs", "evidence", "locations", "timeline"):
        items = script[key]
        if not isinstance(items, list) or not items:
            raise ValueError(f"{key} must be a nonempty list")
        values = [item["id"] for item in items]
        if any(not isinstance(value, str) or not value for value in values) or len(set(values)) != len(values):
            raise ValueError(f"Invalid or duplicate IDs in {key}")
        ids[key] = set(values)
    if len(ids["npcs"]) < 2 or script["killer"] not in ids["npcs"]:
        raise ValueError("Invalid roles or killer")
    validate_mode(script["mode"], ids["evidence"], ids["npcs"])
    limit = script["searchLimit"]
    if type(limit) is not int or not 1 <= limit <= len(script["locations"]):
        raise ValueError("Invalid searchLimit")

    def evidence_refs(values: Any) -> None:
        if not isinstance(values, list) or any(not isinstance(value, str) or value not in ids["evidence"] for value in values):
            raise ValueError("Unknown evidence reference")

    evidence_refs(script["publicEvidence"])
    for item in script["evidence"]:
        if item.get("kind", "material") not in {"material", "testimony"}:
            raise ValueError("Unknown evidence kind")
        for key in ("title", "summary", "detail"):
            if not isinstance(item[key], str) or not item[key].strip():
                raise ValueError(f"Invalid evidence {key}")
    for item in script["timeline"]:
        for key in ("time", "title", "detail"):
            if not isinstance(item[key], str) or not item[key].strip():
                raise ValueError(f"Invalid timeline {key}")
        if type(item["unlocked_by_default"]) is not bool:
            raise ValueError("Invalid timeline visibility")
    for location in script["locations"]:
        for key in ("name", "description"):
            if not isinstance(location[key], str) or not location[key].strip():
                raise ValueError(f"Invalid location {key}")
        evidence_refs(location["evidence"])
    for npc in script["npcs"]:
        for key in ("name", "role", "public_profile", "private_secret", "strategy"):
            if not isinstance(npc[key], str) or not npc[key].strip():
                raise ValueError(f"Invalid role {key}")
        if npc["initial_emotion"] not in {"冷静", "烦躁", "戒备", "紧绷", "防守", "松动", "配合", "慌张"}:
            raise ValueError("Invalid initial emotion")
        if not isinstance(npc["facts"], list) or not npc["facts"] or any(not isinstance(fact, str) for fact in npc["facts"]):
            raise ValueError("Invalid facts")
        book = npc["book"]
        if not isinstance(book["intro"], str) or not book["intro"].strip():
            raise ValueError("Invalid book intro")
        if "approach" in book and (not isinstance(book["approach"], str) or not book["approach"].strip()):
            raise ValueError("Invalid book approach")
        evidence_refs(book["starting"])
        evidence_refs(book["search"])
        if set(book["relationships"]) != ids["npcs"] - {npc["id"]}:
            raise ValueError("Relationships must describe every other role")
        if any(not isinstance(value, str) for value in book["relationships"].values()):
            raise ValueError("Invalid relationship")
        if not isinstance(book["goals"], list) or not book["goals"]:
            raise ValueError("Missing personal goals")
        for goal in book["goals"]:
            if not isinstance(goal["title"], str) or not goal["title"].strip():
                raise ValueError("Invalid goal title")
            if goal.get("type") == "narrative":
                if "condition" in goal:
                    raise ValueError("Narrative goals cannot have automated conditions")
            else:
                validate_condition(goal.get("condition"), ids["evidence"], ids["npcs"])
    for location in script["locations"]:
        if "phases" in location:
            phases = {phase["id"] for phase in script["mode"]["phases"] if "search" in phase["actions"]}
            if (not isinstance(location["phases"], list) or not location["phases"]
                    or any(p not in phases for p in location["phases"])):
                raise ValueError("Unknown location search phase")


def load_scripts() -> dict[str, dict[str, Any]]:
    scripts = {}
    for path in sorted(SCRIPT_DIR.glob("*.json")):
        try:
            script = json.loads(path.read_text(encoding="utf-8"))
            validate_script(script)
            if script["id"] in scripts:
                raise ValueError("Duplicate script ID")
            scripts[script["id"]] = script
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"Invalid script {path.name}: {exc}") from exc
    if DEFAULT_SCRIPT_ID not in scripts:
        raise ValueError("Default script not found")
    return scripts
