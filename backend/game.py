from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import RLock
from typing import Any, Callable
from uuid import uuid4

if __package__:
    from .scripts import script_summary
    from .rules import goal_complete, normalize_rules
else:
    from scripts import script_summary
    from rules import goal_complete, normalize_rules


class GameError(Exception):
    def __init__(self, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.status = status


class Game:
    def __init__(self, case: dict[str, Any], generate: Callable[..., dict[str, Any]]) -> None:
        normalize_rules(case)
        self.case = case
        self.phases = case["mode"]["phases"]
        self.books = {npc["id"]: npc.get("book", {}) for npc in case["npcs"]}
        self.locations = case.get("locations", [])
        self.search_limit = case["searchLimit"]
        self.generate = generate
        self.lock = RLock()
        self.version = 0
        self.initiative_running = False
        self.data = self.initial()

    def initial(self) -> dict[str, Any]:
        return {
            "sessionId": str(uuid4()), "responses": {},
            "player": None, "playMode": "roleplay", "phase": 0, "hands": {}, "public": set(self.case.get("publicEvidence", [])),
            "privateChats": {}, "board": [], "memories": {}, "emotions": {},
            "searched": [], "pending": [], "discussionCount": 0, "votes": {},
            "initiativeQueue": [], "privateInvitations": [], "phaseSearches": {},
        }

    def phase_config(self, data: dict[str, Any] | None = None) -> dict[str, Any]:
        data = self.data if data is None else data
        return self.phases[data["phase"] - 1] if data["phase"] else {
            "id": "lobby", "kind": "lobby", "label": "选择角色",
            "objective": "选择一个角色，领取只属于你的剧本。", "actions": [],
        }

    def searches_left(self, data: dict[str, Any]) -> int:
        phase = self.phase_config(data)
        remaining = self.search_limit - len(data["searched"])
        if "searchLimit" in phase:
            remaining = min(remaining, phase["searchLimit"] - data["phaseSearches"].get(phase["id"], 0))
        return max(0, remaining)

    def accusation_readiness(self, data: dict[str, Any]) -> dict[str, Any] | None:
        phase = data["phase"]
        if not phase or phase >= len(self.phases) or self.phases[phase]["kind"] != "accusation":
            return None
        config = self.phase_config(data)
        unsearched = [location for location in self.locations if location["id"] not in data["searched"]]
        available = [location for location in unsearched
                     if "search" in config["actions"] and
                     ("phases" not in location or config["id"] in location["phases"])]
        searches_available = min(self.searches_left(data), len(available))
        new_public = len(data["public"] - set(self.case.get("publicEvidence", [])))
        warnings = []
        if searches_available:
            warnings.append(f"本阶段还能搜证或补查 {searches_available} 个地点，尚未调查完。")
        elif unsearched and len(data["searched"]) < self.search_limit:
            warnings.append(f"还有 {len(unsearched)} 个地点未搜索，但本阶段已不开放或已用完搜索配额。")
        if new_public < 2:
            warnings.append(f"除初始公共线索外，目前只新增公开 {new_public} 条线索；各角色可能缺乏判断依据。")
        return {"searchedCount": len(data["searched"]), "unsearchedCount": len(unsearched),
                "searchesAvailable": searches_available, "publicEvidenceCount": len(data["public"]),
                "newPublicEvidenceCount": new_public, "warnings": warnings}

    def person(self, role_id: str) -> dict[str, Any]:
        for npc in self.case["npcs"]:
            if npc["id"] == role_id:
                return npc
        raise GameError("请选择本局中的角色。", 400)

    def evidence(self, ids: set[str] | list[str]) -> list[dict[str, Any]]:
        return [{key: item[key] for key in ("id", "title", "summary", "detail")}
                | {"kind": item.get("kind", "material")}
                for item in self.case.get("evidence", []) if item["id"] in ids]

    def host(self, data: dict[str, Any], text: str) -> None:
        data["board"].append({
            "id": len(data["board"]), "speakerId": "host", "speakerName": "主持人",
            "text": text, "phase": data["phase"], "evidenceIds": [],
        })

    def public_person(self, npc: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        return {"id": npc["id"], "name": npc["name"], "role": npc["role"],
                "publicProfile": npc["public_profile"],
                "emotion": data["emotions"].get(npc["id"], npc["initial_emotion"])}

    def state(self) -> dict[str, Any]:
        with self.lock:
            data = self.data
            player_id = data["player"]
            phase = data["phase"]
            config = self.phase_config(data)
            player = self.person(player_id) if player_id else None
            result = {
                "case": {**script_summary(self.case),
                         "opening": self.case.get("opening", self.case["summary"]),
                         "timeline": [{key: event[key] for key in ("time", "title", "detail")}
                                      for event in self.case.get("timeline", []) if event["unlocked_by_default"]]},
                "roles": [self.public_person(npc, data) for npc in self.case["npcs"]],
                "player": None,
                "playMode": data["playMode"],
                "phase": phase,
                "phaseId": config["id"], "phaseKind": config["kind"],
                "phaseLabel": config["label"], "objective": config["objective"],
                "allowedActions": config["actions"],
                "nextPhase": ({key: self.phases[phase][key] for key in ("id", "kind", "label")}
                              if phase and config["kind"] not in {"accusation", "reveal"} else None),
                "phases": [item["label"] for item in self.phases],
                "npcs": [self.public_person(npc, data) for npc in self.case["npcs"] if npc["id"] != player_id],
                "privateChats": data["privateChats"],
                "privateInvitations": [item for item in data["privateInvitations"]
                                       if item["status"] in {"pending", "deferred"}],
                "initiativeQueue": data["initiativeQueue"],
                "board": data["board"],
                "hand": self.evidence(data["hands"].get(player_id, set())),
                "publicEvidence": self.evidence(data["public"]),
                "locations": [{key: location[key] for key in ("id", "name", "description")}
                              | {"searched": location["id"] in data["searched"],
                                 "available": "search" in config["actions"] and
                                    ("phases" not in location or config["id"] in location["phases"])}
                              for location in self.locations],
                "searchesLeft": self.searches_left(data),
                "pendingSpeakers": data["pending"],
                "discussionCount": data["discussionCount"],
                "playerVote": data["votes"].get(player_id, {}).get("targetId"),
                "accusationReadiness": self.accusation_readiness(data),
                "result": self.result(data) if config["kind"] == "reveal" else None,
            }
            if player:
                book = self.books[player_id]
                result["player"] = {
                    **self.public_person(player, data), "intro": book["intro"],
                    "secret": player["private_secret"], "facts": player["facts"],
                    "approach": book.get("approach", player["strategy"]),
                    "goals": [goal["title"] for goal in book["goals"]], "relationships": book["relationships"],
                }
            return deepcopy(result)

    def reset(self) -> dict[str, Any]:
        with self.lock:
            self.data = self.initial()
            self.version += 1
            return self.state()

    def ready(self, action: str, pending_ok: bool = False) -> None:
        if not self.data["player"] or action not in self.phase_config()["actions"]:
            raise GameError("当前轮次不能进行这个操作。")
        if self.data["pending"] and not pending_ok:
            raise GameError("请先等待或继续完成其他人的发言。")

    def start(self, role_id: str | None = None, *, mode: str = "roleplay") -> dict[str, Any]:
        with self.lock:
            if self.case["availability"]["status"] != "ready":
                raise GameError(self.case["availability"]["note"] or "这个剧本尚缺完整材料，暂不能开局。")
            if mode not in {"roleplay", "killer"}:
                raise GameError("未知的扮演模式。", 400)
            if mode == "killer":
                role_id = self.case["killer"]
            self.person(role_id)
            if self.data["player"]:
                raise GameError("本局已经开始。如需更换角色，请重开。")
            self.data["player"] = role_id
            self.data["playMode"] = mode
            self.data["phase"] = 1
            self.data["hands"] = {key: set(book["starting"]) for key, book in self.books.items()}
            self.data["privateChats"] = {npc["id"]: [] for npc in self.case["npcs"] if npc["id"] != role_id}
            self.enter_phase()
            self.host(self.data, "请领取自己的剧本。角色秘密只对本人可见，私聊不会自动变成公开发言。")
            self.version += 1
            return self.state()

    def advance(self, *, confirm_accusation: bool = False) -> dict[str, Any]:
        with self.lock:
            if not self.data["player"] or self.phase_config()["kind"] in {"accusation", "reveal"}:
                raise GameError("当前轮次不能推进。")
            if self.data["pending"]:
                raise GameError("请先完成其他人的发言。")
            if self.accusation_readiness(self.data) is not None and confirm_accusation is not True:
                raise GameError("请先查看指认前提醒，并确认结束调查后再进入指认。")
            self.data["phase"] += 1
            self.enter_phase()
            self.host(self.data, self.phase_config()["objective"])
            self.version += 1
            return self.state()

    def enter_phase(self) -> None:
        """Apply only the current story's entry effects, exactly once."""
        config = self.phase_config()
        self.data["public"].update(config.get("publicEvidence", []))
        for role_id, ids in config.get("privateEvidence", {}).items():
            self.data["hands"][role_id].update(ids)
        if config.get("distributeSearch"):
            for role_id, book in self.books.items():
                if role_id != self.data["player"]:
                    self.data["hands"][role_id].update(book["search"])
        if "discuss" in config["actions"]:
            self.queue_discussion()
        if "initiative" in config["actions"]:
            active = {item["npcId"] for item in self.data["privateInvitations"]
                      if item["status"] in {"pending", "deferred"}}
            self.data["initiativeQueue"] = [
                npc["id"] for npc in self.case["npcs"]
                if npc["id"] != self.data["player"] and npc["id"] not in active
            ]
        else:
            self.data["initiativeQueue"] = []
        if "private" not in config["actions"]:
            for item in self.data["privateInvitations"]:
                if item["status"] in {"pending", "deferred"}:
                    item["status"] = "expired"

    def search(self, location_id: str) -> dict[str, Any]:
        with self.lock:
            self.ready("search")
            location = next((item for item in self.locations if item["id"] == location_id), None)
            if not location:
                raise GameError("这个地点不存在。", 400)
            if "phases" in location and self.phase_config()["id"] not in location["phases"]:
                raise GameError("这个地点尚未开放搜证。")
            if location_id in self.data["searched"] or not self.searches_left(self.data):
                raise GameError("这个地点已经搜过，或本轮搜证次数已用完。")
            self.data["searched"].append(location_id)
            phase_id = self.phase_config()["id"]
            self.data["phaseSearches"][phase_id] = self.data["phaseSearches"].get(phase_id, 0) + 1
            self.data["hands"][self.data["player"]].update(location["evidence"])
            self.version += 1
            return self.state()

    def publish(self, evidence_id: str) -> dict[str, Any]:
        with self.lock:
            self.ready("publish")
            if evidence_id not in self.data["hands"][self.data["player"]]:
                raise GameError("你只能公开自己持有的线索。", 400)
            if evidence_id not in self.data["public"]:
                self.data["public"].add(evidence_id)
                evidence = self.evidence([evidence_id])[0]
                player = self.person(self.data["player"])
                self.host(self.data, f"{player['name']}公开了「{evidence['title']}」。")
                self.version += 1
            return self.state()

    def queue_discussion(self) -> None:
        seats = [npc["id"] for npc in self.case["npcs"] if npc["id"] != self.data["player"]]
        offset = self.data["discussionCount"] % len(seats)
        self.data["pending"] = seats[offset:] + seats[:offset]
        self.data["discussionCount"] += 1

    def discuss(self, message: str) -> dict[str, Any]:
        if len(message) > 2000:
            raise GameError("发言最多 2000 字。", 400)
        with self.lock:
            self.ready("discuss")
            if message.strip():
                player = self.person(self.data["player"])
                self.data["board"].append({
                    "id": len(self.data["board"]), "speakerId": player["id"],
                    "speakerName": player["name"], "text": message.strip(),
                    "phase": self.data["phase"], "evidenceIds": [],
                })
            else:
                self.host(self.data, "请继续讨论。可以回应上一位的说法，也可以主动质疑、解释或寻求合作。")
            self.queue_discussion()
            self.version += 1
            return self.state()

    def context(self, data: dict[str, Any], npc_id: str, mode: str) -> dict[str, Any]:
        npc = self.person(npc_id)
        player = self.person(data["player"])
        visible = data["public"] | data["hands"][npc_id]
        return {
            "sessionId": data["sessionId"],
            "scriptId": self.case["id"],
            "lastResponseId": data["responses"].get(npc_id),
            "mode": mode,
            "caseBackground": {"title": self.case["title"],
                               "summary": self.case["summary"],
                               "opening": self.case.get("opening", self.case["summary"]),
                               "publicTimeline": [event for event in self.case["timeline"] if event["unlocked_by_default"]],
                               "people": [{"id": p["id"], "name": p["name"], "role": p["role"]} for p in self.case["npcs"]]},
            "yourCharacter": {**{key: value for key, value in npc.items() if key != "book"},
                              **self.books[npc_id]},
            "playerCharacter": {"id": player["id"], "name": player["name"], "role": player["role"],
                                "publicProfile": player["public_profile"]},
            "yourMemory": data["memories"].get(npc_id, ""),
            "yourEmotion": data["emotions"].get(npc_id, npc["initial_emotion"]),
            "privateInvitations": [item for item in data["privateInvitations"] if item["npcId"] == npc_id],
            "round": self.phase_config(data)["label"],
            "rules": {"mode": self.case["mode"]["label"],
                      "objective": self.phase_config(data)["objective"],
                      "allowedActions": self.phase_config(data)["actions"]},
            "publicDiscussion": data["board"][-30:],
            "knownEvidence": self.evidence(visible),
            "publicEvidence": self.evidence(data["public"]),
            "availableEvidence": self.evidence(data["hands"][npc_id] - data["public"]),
            "voteOptions": [p["id"] for p in self.case["npcs"]] if mode == "vote" else [],
        }

    def snapshot(self) -> tuple[dict[str, Any], int]:
        return deepcopy(self.data), self.version

    def check_version(self, version: int) -> None:
        if version != self.version:
            raise GameError("本局在回答期间发生了变化，本轮未保存，请重试。")

    def private(self, npc_id: str, message: str) -> dict[str, Any]:
        if not message.strip() or len(message) > 2000:
            raise GameError("私聊内容不能为空，且最多 2000 字。", 400)
        self.person(npc_id)
        with self.lock:
            self.ready("private")
            if npc_id == self.data["player"]:
                raise GameError("请选择另一位角色私聊。", 400)
            data, version = self.snapshot()
        generated = self.generate(self.context(data, npc_id, "private"),
                                  data["privateChats"][npc_id], message)
        with self.lock:
            self.check_version(version)
            shared = set(generated["evidenceIds"]) & self.data["hands"][npc_id]
            self.data["privateChats"][npc_id].append({
                "npcId": npc_id, "npcName": self.person(npc_id)["name"],
                "question": message.strip(), "response": generated["reply"],
                "evidenceIds": sorted(shared),
            })
            # Sharing in private gives the player a clue, not everyone at the table.
            self.data["hands"][self.data["player"]].update(shared)
            self.data["memories"][npc_id] = generated["memory"]
            self.data["responses"][npc_id] = generated.get("_responseId")
            self.data["emotions"][npc_id] = generated["emotion"]
            self.version += 1
            return {"reply": generated["reply"], "state": self.state()}

    def initiative(self) -> dict[str, Any]:
        """Assess a snapshot concurrently and commit successful roles together."""
        with self.lock:
            self.ready("initiative")
            if self.initiative_running:
                raise GameError("角色们正在判断邀约，请等待本次完成。")
            if not self.data["initiativeQueue"]:
                return {"invitation": None, "invitations": [], "errors": [], "state": self.state()}
            data, version = self.snapshot()
            self.initiative_running = True

        def assess(npc_id: str) -> dict[str, Any]:
            generated = self.generate(
                self.context(data, npc_id, "invite"), data["privateChats"][npc_id],
                "现在是自由交流间隙。请独立判断是否主动约玩家私聊，"
                "考虑你的目标、关系和当前局势，不要为了邀约而邀约。"
                "wantsPrivateChat写你的决定；愿意时reply为不超过200字的简短邀约，"
                "此时不交付线索，evidenceIds为[]，不假设玩家已经答应。",
            )
            if type(generated.get("wantsPrivateChat")) is not bool or generated["evidenceIds"]:
                raise GameError("角色邀约格式无效，本轮未保存。", 502)
            return generated

        try:
            results, errors = {}, []
            with ThreadPoolExecutor(max_workers=len(data["initiativeQueue"])) as executor:
                futures = {npc_id: executor.submit(assess, npc_id) for npc_id in data["initiativeQueue"]}
                for npc_id, future in futures.items():
                    try:
                        results[npc_id] = future.result()
                    except Exception as exc:
                        if not hasattr(exc, "status"):
                            raise
                        errors.append({"npcId": npc_id, "npcName": self.person(npc_id)["name"],
                                       "message": str(exc)})
            with self.lock:
                self.check_version(version)
                invitations = []
                for npc_id, generated in results.items():
                    self.data["initiativeQueue"].remove(npc_id)
                    self.data["memories"][npc_id] = generated["memory"]
                    self.data["responses"][npc_id] = generated.get("_responseId")
                    self.data["emotions"][npc_id] = generated["emotion"]
                    if generated["wantsPrivateChat"]:
                        invitation = {
                            "id": str(uuid4()), "npcId": npc_id, "npcName": self.person(npc_id)["name"],
                            "message": generated["reply"], "status": "pending", "phase": data["phase"],
                        }
                        self.data["privateInvitations"].append(invitation)
                        invitations.append(invitation)
                if results:
                    self.version += 1
                return {"invitation": deepcopy(invitations[0]) if invitations else None,
                        "invitations": deepcopy(invitations), "errors": errors, "state": self.state()}
        finally:
            with self.lock:
                self.initiative_running = False

    def respond_invitation(self, invitation_id: str, decision: str) -> dict[str, Any]:
        if decision not in {"accept", "decline", "later"}:
            raise GameError("请选择接受、婉拒或稍后回复。", 400)
        with self.lock:
            self.ready("private")
            invitation = next((item for item in self.data["privateInvitations"] if item["id"] == invitation_id), None)
            if not invitation or invitation["status"] not in {"pending", "deferred"}:
                raise GameError("这条邀约不存在或已经处理。")
            if decision != "accept":
                invitation["status"] = "declined" if decision == "decline" else "deferred"
                self.version += 1
                return self.state()
            data, version = self.snapshot()
            npc_id = invitation["npcId"]
            context = self.context(data, npc_id, "private")
            context["privateInitiative"] = deepcopy(invitation)
        generated = self.generate(
            context, data["privateChats"][npc_id],
            "玩家已接受你的私聊邀约。现在由你主动开场，谈谈你想找他商量的事。"
            "这不是玩家透露案情，也不代表他同意结盟或交换线索。请根据自己的目标自然开口。",
        )
        with self.lock:
            self.check_version(version)
            invitation["status"] = "accepted"
            shared = set(generated["evidenceIds"]) & self.data["hands"][npc_id]
            self.data["privateChats"][npc_id].append({
                "npcId": npc_id, "npcName": self.person(npc_id)["name"],
                "question": "", "response": generated["reply"], "initiator": "npc",
                "evidenceIds": sorted(shared),
            })
            self.data["hands"][self.data["player"]].update(shared)
            self.data["memories"][npc_id] = generated["memory"]
            self.data["responses"][npc_id] = generated.get("_responseId")
            self.data["emotions"][npc_id] = generated["emotion"]
            self.version += 1
            return {"reply": generated["reply"], "state": self.state()}

    def vote(self, target_id: str) -> dict[str, Any]:
        self.person(target_id)
        with self.lock:
            self.ready("vote")
            if self.data["player"] in self.data["votes"]:
                raise GameError("你已经投票，等待其他人完成指认。")
            self.data["votes"][self.data["player"]] = {"targetId": target_id, "reason": "玩家的独立指认"}
            self.data["pending"] = [p["id"] for p in self.case["npcs"] if p["id"] != self.data["player"]]
            self.version += 1
            return self.state()

    def ai_turn(self) -> dict[str, Any]:
        with self.lock:
            self.ready("vote" if self.phase_config()["kind"] == "accusation" else "discuss", pending_ok=True)
            if not self.data["pending"]:
                raise GameError("当前没有等待发言的角色。")
            data, version = self.snapshot()
            npc_id = data["pending"][0]
        mode = "vote" if self.phase_config(data)["kind"] == "accusation" else "public"
        prompt = ("请独立指认。仅依据你自己的经历、私聊记忆和已经公开的信息，"
                  "在voteId中填写你的选择，reply写简短理由，区分确知事实与尚未证实的怀疑。"
                  "信息不足时明确说明判断有限，仍按当前已知信息作出选择。"
                  "不能为了给投票找理由编造证据、目击或供认；不要读取其他人的秘密或投票。"
                  if mode == "vote" else
                  "轮到你在桌上公开发言。回应最新的发言或线索，主动试探、质疑、解释或争取合作。"
                  "不要把玩家当侦探，不必等待他发问。其他人将会听到你的这段话。")
        generated = self.generate(self.context(data, npc_id, mode),
                                  data["privateChats"][npc_id], prompt)
        if mode == "vote" and generated.get("voteId") not in self.books:
            raise GameError("角色返回的投票无效，请重试。", 502)
        with self.lock:
            self.check_version(version)
            self.data["pending"].pop(0)
            self.data["memories"][npc_id] = generated["memory"]
            self.data["responses"][npc_id] = generated.get("_responseId")
            self.data["emotions"][npc_id] = generated["emotion"]
            if mode == "vote":
                self.data["votes"][npc_id] = {"targetId": generated["voteId"], "reason": generated["reply"]}
                if not self.data["pending"]:
                    self.data["phase"] += 1
                    self.enter_phase()
                    self.host(self.data, "所有人的指认已经完成。现在同时揭晓投票与真相。")
            else:
                shared = set(generated["evidenceIds"]) & self.data["hands"][npc_id]
                self.data["public"].update(shared)
                npc = self.person(npc_id)
                self.data["board"].append({
                    "id": len(self.data["board"]), "speakerId": npc_id, "speakerName": npc["name"],
                    "text": generated["reply"], "phase": self.data["phase"], "evidenceIds": sorted(shared),
                })
            self.version += 1
            return {"reply": generated["reply"] if mode == "public" else None, "state": self.state()}

    def result(self, data: dict[str, Any]) -> dict[str, Any]:
        counts = Counter(vote["targetId"] for vote in data["votes"].values())
        maximum = max(counts.values(), default=0)
        leaders = [role_id for role_id, count in counts.items() if count == maximum]
        accused = leaders[0] if len(leaders) == 1 else None
        killer = self.case["killer"]
        player_id = data["player"]
        book = self.books[player_id]
        goals = []
        for goal in book["goals"]:
            complete = (None if goal.get("type") == "narrative" else
                        goal_complete(goal["condition"], data, player_id, killer, accused))
            goals.append({"title": goal["title"], "complete": complete})
        return {
            "votes": [{"voterId": role_id, "voterName": self.person(role_id)["name"],
                       "targetId": vote["targetId"], "targetName": self.person(vote["targetId"])["name"],
                       "reason": vote["reason"]} for role_id, vote in data["votes"].items()],
            "accusedName": self.person(accused)["name"] if accused else None,
            "tiedNames": [self.person(role_id)["name"] for role_id in leaders] if not accused else [],
            "groupSolved": accused == killer if counts else None, "goals": goals,
            "truth": self.case["truth"],
            "timeline": [{key: event[key] for key in ("time", "title", "detail")} for event in self.case["timeline"]],
            "characters": [{
                "id": npc["id"], "name": npc["name"], "role": npc["role"],
                "isPlayer": npc["id"] == player_id, "isKiller": npc["id"] == killer,
                "publicProfile": npc["public_profile"], "intro": self.books[npc["id"]]["intro"],
                "secret": npc["private_secret"], "facts": list(npc["facts"]),
                "approach": self.books[npc["id"]].get("approach", npc["strategy"]),
                "relationships": [
                    {"roleId": role_id, "name": self.person(role_id)["name"], "description": description}
                    for role_id, description in self.books[npc["id"]]["relationships"].items()
                ],
                "goals": [goal["title"] for goal in self.books[npc["id"]]["goals"]],
                "evidenceIds": list(dict.fromkeys(
                    self.books[npc["id"]]["starting"] + self.books[npc["id"]]["search"])),
            } for npc in self.case["npcs"]],
            # Reveal source clues without granting hands or making them public in the game.
            "evidence": self.evidence([item["id"] for item in self.case.get("evidence", [])]),
        }
