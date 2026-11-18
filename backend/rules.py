"""Declarative phases and goal conditions shared by every story."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

ACTIONS = {"private", "initiative", "search", "publish", "discuss", "vote", "act"}
KINDS = {"reading", "exchange", "search", "discussion", "accusation", "reveal"}
CLASSIC_MODE = {
    "id": "classic", "label": "六幕剧本杀",
    "phases": [
        {"id": "reading", "kind": "reading", "label": "读本",
         "objective": "读完你的剧本。你也有秘密，不必把所有事情都告诉别人。", "actions": []},
        {"id": "private", "kind": "exchange", "label": "私聊",
         "objective": "找一位角色交换信息、试探立场，或者争取一个盟友。",
         "actions": ["private", "initiative"]},
        {"id": "search", "kind": "search", "label": "搜证",
         "objective": "搜索地点。带回的线索先只属于你。",
         "actions": ["private", "initiative", "search"]},
        {"id": "discussion", "kind": "discussion", "label": "公聊",
         "objective": "选择公开哪些线索，解释自己的嫌疑，听其他人互相质疑。",
         "actions": ["private", "initiative", "publish", "discuss"], "distributeSearch": True},
        {"id": "vote", "kind": "accusation", "label": "指认",
         "objective": "独立投票。其他人的选择会在所有投票结束后一起揭晓。", "actions": ["vote"]},
        {"id": "reveal", "kind": "reveal", "label": "复盘",
         "objective": "真相与个人目标揭晓。", "actions": []},
    ],
}

LEGACY_GOALS = {
    "avoid_accusation": "not_accused", "vote_killer": "vote_killer",
    "publish_evidence": "evidence_public", "hide_evidence": "evidence_hidden",
}
CHECKS = set(LEGACY_GOALS.values()) | {"evidence_held", "private_contact"}


def normalize_rules(script: dict[str, Any]) -> None:
    """Upgrade old story files in memory, without rewriting their content."""
    script.setdefault("schemaVersion", 2)
    script.setdefault("availability", {"status": "ready", "note": ""})
    script.setdefault("mode", deepcopy(CLASSIC_MODE))
    for npc in script.get("npcs", []):
        for goal in npc.get("book", {}).get("goals", []):
            if goal.get("type") in LEGACY_GOALS and "condition" not in goal:
                goal["condition"] = {"check": LEGACY_GOALS[goal["type"]]}
                if "evidenceId" in goal:
                    goal["condition"]["evidenceId"] = goal["evidenceId"]


def validate_condition(condition: Any, evidence_ids: set[str], role_ids: set[str]) -> None:
    if not isinstance(condition, dict):
        raise ValueError("Goal condition must be an object")
    for operator in ("all", "any"):
        if operator in condition:
            if set(condition) != {operator} or not isinstance(condition[operator], list) or not condition[operator]:
                raise ValueError("Goal all/any needs nonempty conditions")
            for child in condition[operator]:
                validate_condition(child, evidence_ids, role_ids)
            return
    if "not" in condition:
        if set(condition) != {"not"}:
            raise ValueError("Invalid goal negation")
        validate_condition(condition["not"], evidence_ids, role_ids)
        return
    check = condition.get("check")
    if not isinstance(check, str) or check not in CHECKS:
        raise ValueError("Unknown goal condition")
    expected = {"check"}
    if check.startswith("evidence_"):
        expected.add("evidenceId")
        if condition.get("evidenceId") not in evidence_ids:
            raise ValueError("Unknown goal evidence")
    elif check == "private_contact":
        expected.add("roleId")
        if condition.get("roleId") not in role_ids:
            raise ValueError("Unknown goal role")
    if set(condition) != expected:
        raise ValueError("Unexpected goal condition field")


def validate_mode(mode: Any, evidence_ids: set[str], role_ids: set[str]) -> None:
    if not isinstance(mode, dict) or not all(isinstance(mode.get(k), str) and mode[k].strip() for k in ("id", "label")):
        raise ValueError("Invalid mode")
    phases = mode.get("phases")
    if not isinstance(phases, list) or len(phases) < 2:
        raise ValueError("Mode needs at least reading and reveal phases")
    seen = set()
    for index, phase in enumerate(phases):
        if not isinstance(phase, dict):
            raise ValueError("Invalid phase")
        for key in ("id", "label", "objective"):
            if not isinstance(phase.get(key), str) or not phase[key].strip():
                raise ValueError(f"Invalid phase {key}")
        if phase["id"] in seen or phase.get("kind") not in KINDS:
            raise ValueError("Duplicate phase ID or unknown phase kind")
        seen.add(phase["id"])
        actions = phase.get("actions")
        if not isinstance(actions, list) or any(not isinstance(a, str) or a not in ACTIONS for a in actions):
            raise ValueError("Unknown phase action")
        if len(actions) != len(set(actions)):
            raise ValueError("Duplicate phase action")
        if ("vote" in actions) != (phase["kind"] == "accusation"):
            raise ValueError("Only an accusation phase may allow voting")
        if phase["kind"] == "accusation" and (index != len(phases) - 2 or actions != ["vote"]):
            raise ValueError("Secret voting must immediately precede reveal")
        if phase["kind"] == "reveal" and (index != len(phases) - 1 or actions):
            raise ValueError("Reveal must be final and have no actions")
        if "initiative" in actions and "private" not in actions:
            raise ValueError("Invitations require private chat")
        if "searchLimit" in phase and (type(phase["searchLimit"]) is not int or phase["searchLimit"] < 1 or "search" not in actions):
            raise ValueError("Invalid phase search quota")
        if "distributeSearch" in phase and type(phase["distributeSearch"]) is not bool:
            raise ValueError("Invalid NPC search distribution")
        public = phase.get("publicEvidence", [])
        private = phase.get("privateEvidence", {})
        if not isinstance(public, list) or any(e not in evidence_ids for e in public):
            raise ValueError("Unknown phase public evidence")
        if not isinstance(private, dict):
            raise ValueError("Invalid phase private evidence")
        for role_id, values in private.items():
            if role_id not in role_ids or not isinstance(values, list) or any(e not in evidence_ids for e in values):
                raise ValueError("Unknown phase private evidence")
    if phases[0]["kind"] != "reading" or phases[0]["actions"] or phases[-1]["kind"] != "reveal":
        raise ValueError("Mode must begin with reading and end with reveal")


def public_mode(mode: dict[str, Any]) -> dict[str, Any]:
    # Entry effects contain private evidence assignments, never send them to UI.
    return {"id": mode["id"], "label": mode["label"], "phases": [
        {key: phase[key] for key in ("id", "kind", "label", "objective", "actions", "searchLimit") if key in phase}
        for phase in mode["phases"]
    ]}


def goal_complete(condition: dict[str, Any], data: dict[str, Any], actor: str,
                  killer: str, accused: str | None) -> bool:
    if "all" in condition:
        return all(goal_complete(c, data, actor, killer, accused) for c in condition["all"])
    if "any" in condition:
        return any(goal_complete(c, data, actor, killer, accused) for c in condition["any"])
    if "not" in condition:
        return not goal_complete(condition["not"], data, actor, killer, accused)
    check = condition["check"]
    if check == "not_accused":
        return accused != actor
    if check == "vote_killer":
        return data["votes"].get(actor, {}).get("targetId") == killer
    if check == "evidence_public":
        return condition["evidenceId"] in data["public"]
    if check == "evidence_hidden":
        return condition["evidenceId"] not in data["public"]
    if check == "evidence_held":
        return condition["evidenceId"] in data["hands"].get(actor, set())
    if check == "private_contact":
        return bool(data["privateChats"].get(condition["roleId"]))
    raise ValueError(f"Unknown condition: {check}")
