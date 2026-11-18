"""Configuration boundary for the finite-turn rule survival engine."""
from string import Formatter

if __package__:
    from .rules import validate_mode
else:
    from rules import validate_mode

FLAGS = {"nameRecorded", "debrisCleared", "powerRestored", "sisterVerified",
         "sisterRescued", "followedVoice", "braceUsed", "shield", "lureActive",
         "cabinetUnlocked", "workerHelping", "memoryConfirmed", "sisterReady"}


def validate_dungeon(script):
    def text(value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Expected nonempty dungeon text")

    def unique(items):
        if not isinstance(items, list) or not items:
            raise ValueError("Expected nonempty dungeon list")
        ids = [item["id"] for item in items]
        for value in ids:
            text(value)
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate dungeon ID")
        return set(ids)

    for key in ("id", "title", "subtitle", "summary", "opening", "duration",
                "difficulty", "locationLabel", "truth"):
        text(script[key])
    if script["schemaVersion"] != 2 or script["theme"] != "hospital":
        raise ValueError("Unsupported dungeon schema or theme")
    if script["availability"]["status"] != "ready":
        raise ValueError("Dungeon must be ready")
    text(script["availability"]["note"])
    if not isinstance(script["tags"], list) or not script["tags"]:
        raise ValueError("Missing dungeon tags")
    for tag in script["tags"]:
        text(tag)
    roles, evidence, locations = (unique(script[key]) for key in ("npcs", "evidence", "locations"))
    cfg = script["dungeon"]
    if cfg["playerId"] not in roles or cfg["startLocation"] not in locations:
        raise ValueError("Unknown player or start location")
    if set(cfg["npcOrder"]) != roles - {cfg["playerId"]} or len(cfg["npcOrder"]) != len(roles) - 1:
        raise ValueError("Invalid NPC order")
    # This engine implements the declared hospital mechanics explicitly.
    if not {"station", "power", "ward307", "ward309"} <= locations:
        raise ValueError("Missing hospital locations")
    if not {"bracelet", "empty_bed", "exit_badge", "roster"} <= evidence:
        raise ValueError("Missing hospital evidence")
    for key in ("maxTurns", "nightAt", "dawnAt", "anomalyLimit"):
        if type(cfg[key]) is not int or cfg[key] <= 0:
            raise ValueError("Invalid dungeon clock")
    if not cfg["nightAt"] < cfg["dawnAt"] < cfg["maxTurns"]:
        raise ValueError("Invalid clock order")
    if (not isinstance(cfg["patrolTurns"], list)
            or len(set(cfg["patrolTurns"])) != len(cfg["patrolTurns"])
            or any(type(t) is not int or not cfg["nightAt"] <= t < cfg["dawnAt"]
                   for t in cfg["patrolTurns"])):
        raise ValueError("Invalid patrol schedule")
    if type(script["searchLimit"]) is not int or script["searchLimit"] != len(locations):
        raise ValueError("Dungeon locations must all be searchable")
    unique(cfg["variants"])
    for variant in cfg["variants"]:
        if variant["sisterRoom"] not in {"ward307", "ward309"} or variant["breaker"] not in {"A", "B"}:
            raise ValueError("Invalid layout")
        if variant["roomNumber"] != variant["sisterRoom"][4:]:
            raise ValueError("Inconsistent room label")
        text(variant["bracelet"])

    def refs(values):
        if not isinstance(values, list) or any(v not in evidence for v in values):
            raise ValueError("Unknown dungeon evidence")

    def requirements(req):
        if not isinstance(req, dict) or set(req) - {"evidence", "missingEvidence", "flags", "notFlag", "minTurn"}:
            raise ValueError("Invalid dungeon requirements")
        for key in ("evidence", "missingEvidence"):
            refs(req.get(key, []))
        if not isinstance(req.get("flags", []), list) or any(f not in FLAGS for f in req.get("flags", [])):
            raise ValueError("Unknown flag")
        if "notFlag" in req and req["notFlag"] not in FLAGS:
            raise ValueError("Unknown flag")
        if "minTurn" in req and (type(req["minTurn"]) is not int or not 0 <= req["minTurn"] < cfg["maxTurns"]):
            raise ValueError("Invalid minimum turn")

    def effects(effect, owned=None):
        if not isinstance(effect, dict) or set(effect) - {"evidence", "flags", "anomaly"}:
            raise ValueError("Unknown dungeon effect")
        refs(effect.get("evidence", []))
        if owned is not None and not set(effect.get("evidence", [])) <= set(owned):
            raise ValueError("NPC cannot create evidence")
        flags = effect.get("flags", {})
        if not isinstance(flags, dict) or any(f not in FLAGS or type(v) is not bool for f, v in flags.items()):
            raise ValueError("Invalid flag effect")
        if type(effect.get("anomaly", 0)) is not int or not 0 <= effect.get("anomaly", 0) <= cfg["anomalyLimit"]:
            raise ValueError("Invalid anomaly effect")
        if owned is not None and ("anomaly" in effect or set(flags) - {
                "braceUsed", "shield", "lureActive", "cabinetUnlocked",
                "workerHelping", "memoryConfirmed", "sisterReady"}):
            raise ValueError("NPC cannot execute player outcomes")

    refs(script["publicEvidence"])
    for item in script["evidence"]:
        for key in ("title", "summary", "detail"):
            text(item[key])
            for _, field, spec, conversion in Formatter().parse(item[key]):
                if field is not None and (field not in {"roomNumber", "bracelet", "breaker"} or spec or conversion):
                    raise ValueError("Invalid evidence template")
        if item.get("kind", "material") not in {"material", "testimony"}:
            raise ValueError("Invalid evidence kind")
    for location in script["locations"]:
        text(location["name"])
        text(location["description"])
        refs(location["evidence"])
    for npc in script["npcs"]:
        for key in ("name", "role", "public_profile", "private_secret", "strategy"):
            text(npc[key])
        if npc["initial_emotion"] not in {"冷静", "烦躁", "戒备", "紧绷", "防守", "松动", "配合", "慌张"}:
            raise ValueError("Invalid emotion")
        if not isinstance(npc["facts"], list) or not npc["facts"]:
            raise ValueError("Missing facts")
        for fact in npc["facts"]:
            text(fact)
        book = npc["book"]
        text(book["intro"])
        refs(book["starting"])
        refs(book["search"])
        if set(book["relationships"]) != (roles - {npc["id"]} if npc["id"] == cfg["playerId"] else set()):
            raise ValueError("Invalid dungeon relationships")
        for relation in book["relationships"].values():
            text(relation)
        if not isinstance(book["goals"], list) or not book["goals"]:
            raise ValueError("Missing goals")
        for goal in book["goals"]:
            text(goal["title"])
            if goal.get("type") != "narrative":
                raise ValueError("Dungeon goals use explicit ending outcomes")
        if npc["id"] != cfg["playerId"]:
            unique(npc["npcActions"])
            if not any(a["id"] == "wait" and not a.get("requires") and not a["effects"]
                       for a in npc["npcActions"]):
                raise ValueError("NPC must have unconditional wait")
            for action in npc["npcActions"]:
                text(action["label"])
                requirements(action.get("requires", {}))
                effects(action["effects"], book["starting"])
    unique(cfg["rules"])
    for rule in cfg["rules"]:
        text(rule["text"])
        text(rule["truth"])
        refs(rule["evidenceIds"])
    unique(script["actions"])
    for action in script["actions"]:
        text(action["label"])
        text(action["description"])
        requirements(action.get("requires", {}))
        effects(action.get("effects", {}))
        if "location" in action and action["location"] not in locations:
            raise ValueError("Unknown action location")
        op = action.get("operation")
        if op not in {None, "breaker", "verify", "leave"}:
            raise ValueError("Unknown operation")
        if op == "breaker" and action.get("value") not in {"A", "B"}:
            raise ValueError("Unknown breaker")
        if type(action.get("cost", 1)) is not int or action.get("cost", 1) != (0 if op == "leave" else 1):
            raise ValueError("Invalid action cost")
        if "dangerous" in action and type(action["dangerous"]) is not bool:
            raise ValueError("Invalid risk marker")
        if op is None:
            text(action["message"])
    validate_mode(script["mode"], evidence, roles)
    if ([p["kind"] for p in script["mode"]["phases"]] != ["reading", "exchange", "reveal"]
            or set(script["mode"]["phases"][1]["actions"]) != {"private", "search", "publish", "act"}):
        raise ValueError("Unsupported dungeon phases")
