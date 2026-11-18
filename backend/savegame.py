"""Local atomic saves, including a one-time import of the former in-memory game."""
import json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4


class GameStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def path(self, game):
        # IDs come from the validated script catalog, never from a file request.
        return self.directory / (game.case["id"] + ".json")

    def save(self, game):
        with game.lock:
            body = json.dumps({"schema": 1, "scriptId": game.case["id"],
                               "version": game.version, "data": game.data},
                              ensure_ascii=False, default=lambda value: sorted(value), indent=2)
            path = self.path(game)
            temp = path.with_suffix("." + str(uuid4()) + ".tmp")
            try:
                temp.write_text(body, encoding="utf-8")
                temp.replace(path)
            finally:
                temp.unlink(missing_ok=True)

    def load(self, game):
        path = self.path(game)
        if not path.exists():
            return False
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("schema") != 1 or raw.get("scriptId") != game.case["id"]:
            raise ValueError(f"Unsupported save: {path.name}")
        data = raw["data"]
        roles = {p["id"] for p in game.case["npcs"]}
        evidence = {e["id"] for e in game.case["evidence"]}
        if (data["player"] not in roles | {None} or type(data["phase"]) is not int
                or not 0 <= data["phase"] <= len(game.phases)
                or not set(data["public"]) <= evidence
                or any(role not in roles or not set(ids) <= evidence for role, ids in data["hands"].items())):
            raise ValueError(f"Invalid save: {path.name}")
        base = game.initial()
        base.update(data)
        base["public"] = set(base["public"])
        base["hands"] = {role: set(ids) for role, ids in base["hands"].items()}
        if "flags" in base:
            base["flags"] = {**game.initial()["flags"], **base["flags"]}
        with game.lock:
            game.data = base
            game.version = raw["version"] + 1
        return True

    def import_public(self, game, state):
        """Preserve discoverable truths/chats from an old, read-only state API."""
        if state["case"]["id"] != game.case["id"] or game.case.get("gameType") != "dungeon":
            raise ValueError("Only the matching hospital game can be imported")
        if not state["player"]:
            return False
        game.start(state["player"]["id"])
        data = game.data
        known = state["hand"] + state["publicEvidence"]
        candidates = []
        for variant in game.case["dungeon"]["variants"]:
            data["variant"] = deepcopy(variant)
            expected = {e["id"]: e for e in game.evidence([e["id"] for e in known], data)}
            # Titles/details may have been edited between engine versions;
            # summaries carry the old hospital layout's observable values.
            if all(e["summary"] == expected[e["id"]]["summary"] for e in known):
                candidates.append(variant)
        if not candidates:
            raise ValueError("Discovered materials disagree with every known layout; old progress retained")
        data["variant"] = deepcopy(state.get("result", {}).get("variant", candidates[0])
                                    if state.get("result") else candidates[0])
        data["phase"] = state["phase"]
        data["public"] = {e["id"] for e in state["publicEvidence"]}
        data["hands"][data["player"]] = {e["id"] for e in state["hand"]}
        data["privateChats"].update(deepcopy(state["privateChats"]))
        data["board"] = deepcopy(state["board"])
        data["searched"] = [l["id"] for l in state["locations"] if l["searched"]]
        data["pending"] = list(state["pendingSpeakers"])
        world = state["world"]
        data.update(turn=world["turn"], anomaly=world["anomaly"], location=world["location"])
        data["flags"].update(world["flags"])
        data["flags"]["memoryConfirmed"] = data["flags"]["sisterVerified"]
        data["flags"]["sisterReady"] = data["flags"]["sisterRescued"]
        if "exit_badge" in data["hands"][data["player"]]:
            data["flags"]["cabinetUnlocked"] = True
        for npc in state["npcs"]:
            id = npc["id"]
            data["emotions"][id] = npc["emotion"]
            history = data["privateChats"].get(id, [])
            for turn in history:
                data["hands"][id].update(turn.get("presentedEvidenceIds", []))
            if history:
                data["memories"][id] = "此前与许舟的真实谈话：" + "\n".join(
                    f"许舟：{t['question']}；本人回答：{t['response']}" for t in history[-5:])[-1950:]
        event = state.get("encounter")
        if event:
            if game.data["encounter"]:
                raise ValueError("Unexpected import encounter")
            if event["kind"] == "search":
                restored = game.investigation_for(event["location"])
            elif event["kind"] == "talk":
                game.approach(event["npcId"])
                restored = data["encounter"]
            else:
                restored = game.action_scene_for(event["source"], event["location"])
                if not restored:
                    if __package__:
                        from .dungeon_events import threat
                    else:
                        from dungeon_events import threat
                    restored = threat(event["source"], event["location"])
            visible = {c["id"] for c in event["choices"]}
            restored.update(id=event["id"], npcId=event["npcId"], log=deepcopy(event["log"]),
                            paid=event.get("paid", False),
                            seen=[c["id"] for c in restored["choices"] if c["id"] not in visible])
            data["encounter"] = restored
            data["sceneCue"] = None
        if state.get("result"):
            data["ending"] = {k: state["result"][k] for k in ("id", "reason")}
        game.version = state["version"] + 1
        self.save(game)
        return True
