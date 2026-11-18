"""Finite-turn survival; model speech cannot redefine physical rules."""
from copy import deepcopy
from secrets import choice
from uuid import uuid4

if __package__:
    from .game import Game, GameError
    from .npc_ai import validate_reply
    from .dungeon_rules import FLAGS
    from .dungeon_events import investigation, action_scene, threat, encounter, option
    from .dungeon_presence import (affordances, person_here, SENSES, BODILY,
                                   NPC_VISIBLE_FLAGS, physical_outcome)
else:
    from game import Game, GameError
    from npc_ai import validate_reply
    from dungeon_rules import FLAGS
    from dungeon_events import investigation, action_scene, threat, encounter, option
    from dungeon_presence import (affordances, person_here, SENSES, BODILY,
                                  NPC_VISIBLE_FLAGS, physical_outcome)


class DungeonGame(Game):
    def initial(self):
        data = super().initial()
        data.update(turn=0, anomaly=0, flags={f: False for f in FLAGS},
                    location=self.case["dungeon"]["startLocation"],
                    variant=deepcopy(choice(self.case["dungeon"]["variants"])),
                    npcCursor=0, ending=None, encounter=None, sceneCue=None,
                    observations={}, relationships={}, intentHistory=[],
                    lastAction=None)
        return data

    def ready(self, action, pending_ok=False):
        super().ready(action, pending_ok)
        if self.data["encounter"] and action not in {"private", "choice", "publish"}:
            raise GameError("先处理眼前的现场，才能前往别处。")

    def request_version(self, version, required=False):
        if version is None and not required:
            return
        if type(version) is not int:
            raise GameError("version 必须是整数。", 400)
        self.check_version(version)

    def choice_reasons(self, item, data):
        flags = data["flags"]
        reasons = []
        if any(not flags[f] for f in item.get("flags", [])):
            reasons.append("尚未取得对方的配合" if data["encounter"]["kind"] != "danger" else "现场条件不满足")
        if item.get("shield") and not flags["shield"]:
            reasons.append("没有可用的护栏")
        owned = data["hands"].get(data["player"], set()) | data["public"]
        if any(e not in owned for e in item.get("evidenceRequired", [])):
            reasons.append("尚未取得本轮接线标签")
        return reasons

    def public_encounter(self, data):
        event = data["encounter"]
        if not event:
            return None
        return {**{k: deepcopy(event[k]) for k in ("id", "kind", "source", "title", "description", "npcId", "log", "location")},
                "paid": event.get("paid", False),
                "choices": [{k: item[k] for k in ("id", "label", "detail", "dangerous") if k in item}
                            | {"available": not self.choice_reasons(item, data),
                               "reasons": self.choice_reasons(item, data)}
                            for item in event["choices"] if item["id"] not in event["seen"]]}

    def open_encounter(self, event):
        if event["source"] == "patrol":
            event["npcId"] = person_here({**self.data, "encounter": None})
        event["id"] = str(uuid4())
        self.data["encounter"] = event
        self.data["location"] = event["location"]
        self.cue(event["npcId"], f"许舟来到现场：{event['title']}。{event['description']}。"
                 "由你主动开口，说眼前具体的一件事或你想让他回答的问题，不要复述他的目标。")

    def investigation_for(self, location):
        return investigation(location, self.data["variant"]["sisterRoom"])

    def action_scene_for(self, action_id, location):
        return action_scene(action_id, location)

    def cue(self, npc_id, text):
        if not npc_id or self.data["ending"]:
            self.data["sceneCue"] = None
            return
        self.data["sceneCue"] = {"id": str(uuid4()), "npcId": npc_id, "text": text}

    def witness(self, text, npc_id=None):
        npc_id = npc_id or person_here(self.data)
        if npc_id:
            records = self.data["observations"].setdefault(npc_id, [])
            records.append({"text": text, "turn": self.data["turn"], "location": self.data["location"]})
            del records[:-30]
            self.cue(npc_id, f"你亲眼看见许舟这样做：{text}。作出现场反应，"
                     "可以阻拦、反问、提具体条件或动手帮忙；不要泛泛提醒谨慎。")

    def scene_entry(self, text, *, speaker_id=None, action_label=None, evidence_ids=None):
        event = self.data["encounter"]
        if event:
            entry = {"text": text, "evidenceIds": evidence_ids or []}
            if speaker_id:
                entry.update(speakerId=speaker_id, speakerName=self.person(speaker_id)["name"],
                             actionLabel=action_label)
            event["log"].append(entry)
        else:
            self.host(self.data, text)

    def can_talk(self, data, npc_id):
        if npc_id != "sister":
            return True
        owned = data["hands"].get(data["player"], set()) | data["public"]
        return data["flags"]["sisterRescued"] or (
            data["location"] == data["variant"]["sisterRoom"] and "bracelet" in owned)

    def evidence(self, ids, data=None):
        data = self.data if data is None else data
        return [{**item, **{k: item[k].format_map(data["variant"])
                           for k in ("title", "summary", "detail")}}
                for item in super().evidence(ids)]

    def accusation_readiness(self, data):
        return None

    def start(self, role_id=None, *, mode="roleplay"):
        if mode != "roleplay" or role_id != self.case["dungeon"]["playerId"]:
            raise GameError("本副本请以临时护工许舟的身份入局。", 400)
        return super().start(role_id)

    def advance(self, *, confirm_accusation=False):
        with self.lock:
            if not self.data["player"] or self.data["phase"] != 1:
                raise GameError("求生阶段由行动推进时间，结局由实际状态决定。")
            return super().advance()

    def world(self, data):
        cfg = self.case["dungeon"]
        minutes = (23 * 60 + data["turn"] * 30) % (24 * 60)
        return {"turn": data["turn"], "maxTurns": cfg["maxTurns"],
                "time": f"{minutes // 60:02d}:{minutes % 60:02d}",
                "anomaly": data["anomaly"], "anomalyLimit": cfg["anomalyLimit"],
                "location": data["location"], "flags": deepcopy(data["flags"]),
                "night": cfg["nightAt"] <= data["turn"] < cfg["dawnAt"],
                "exitOpen": cfg["dawnAt"] <= data["turn"] < cfg["maxTurns"],
                "patrolTurns": cfg["patrolTurns"]}

    def missing(self, action, data, owner=None):
        req = action.get("requires", {})
        owned = data["hands"].get(owner or data["player"], set()) | data["public"]
        reasons = [f"缺少：{self.evidence([e], data)[0]['title']}"
                   for e in req.get("evidence", []) if e not in owned]
        if any(e in owned for e in req.get("missingEvidence", [])):
            reasons.append("已取得材料")
        if any(not data["flags"][f] for f in req.get("flags", [])):
            reasons.append("需先核验身份")
        if data["flags"].get(req.get("notFlag"), False):
            reasons.append("已经完成")
        if data["turn"] < req.get("minTurn", 0):
            reasons.append("出口窗口尚未开启")
        return reasons

    def state(self):
        with self.lock:
            state = super().state()
            state["nextPhase"] = state["nextPhase"] if self.data["phase"] == 1 else None
            state["world"] = self.world(self.data)
            state["version"] = self.version
            state["encounter"] = self.public_encounter(self.data)
            state["sceneCue"] = ({k: self.data["sceneCue"][k] for k in ("id", "npcId")}
                                 if self.data.get("sceneCue") else None)
            state["lastAction"] = deepcopy(self.data.get("lastAction"))
            state["body"] = BODILY[min(self.data["anomaly"], len(BODILY) - 1)]
            state["presentNpcId"] = person_here(self.data)
            for npc in state["npcs"]:
                npc["availableTalk"] = self.can_talk(self.data, npc["id"])
            for loc in state["locations"]:
                loc["available"] = loc["available"] and not self.data["encounter"] and not self.data["pending"]
            state["rules"] = [{"id": r["id"], "text": r["text"]} for r in self.case["dungeon"]["rules"]]
            state["actions"] = [
                {**{k: a[k] for k in ("id", "label", "description", "dangerous") if k in a},
                 "cost": a.get("cost", 1), "location": a.get("location"),
                 "available": self.data["phase"] == 2 and not self.data["pending"] and not self.data["encounter"] and not self.missing(a, self.data),
                 "reasons": self.missing(a, self.data)}
                for a in self.case["actions"]
            ]
            return state

    def apply_effects(self, effects, private=False):
        data = self.data
        ids = effects.get("evidence", [])
        if private:
            data["hands"][data["player"]].update(ids)
        else:
            data["public"].update(ids)
        data["flags"].update(effects.get("flags", {}))
        data["anomaly"] += effects.get("anomaly", 0)

    def tick(self, queue=True, speaker=None):
        data, cfg = self.data, self.case["dungeon"]
        data["turn"] += 1
        if data["turn"] == cfg["nightAt"]:
            self.host(data, "01:00，病院熄灯。巡查开始，护士站的门闩仍然牢固。")
        if data["turn"] in cfg["patrolTurns"]:
            flags = data["flags"]
            if data["location"] == "station" or (flags["powerRestored"] and flags["debrisCleared"]):
                self.host(data, "巡查的脚步经过，你所在的位置安全。")
            else:
                self.open_encounter(threat("patrol", data["location"]))
                self.host(data, "巡查的白袖口出现在门缝。你必须先应对它。")
        if data["anomaly"] >= cfg["anomalyLimit"]:
            self.finish("failure", "异常达到上限，门后的影子取代了你的脚步。")
        elif data["turn"] >= cfg["maxTurns"]:
            self.finish("failure", "07:00，出口窗口关闭，你仍留在病院。")
        else:
            if data["turn"] == cfg["dawnAt"]:
                self.host(data, "05:00，机械出口窗口开启。持编号工牌可以离开，不额外耗时。")
            if queue and speaker and not data["encounter"]:
                data["pending"] = [speaker]

    def finish(self, ending, reason):
        self.data.update(phase=3, pending=[], encounter=None, sceneCue=None, ending={"id": ending, "reason": reason})
        self.host(self.data, reason)

    def search(self, location_id, *, expected_version=None):
        with self.lock:
            self.ready("search")
            self.request_version(expected_version)
            loc = next((l for l in self.locations if l["id"] == location_id), None)
            if loc is None:
                raise GameError("这个地点不存在。", 400)
            if location_id in self.data["searched"]:
                raise GameError("这个地点已经调查过。")
            data = self.data
            self.open_encounter(self.investigation_for(location_id))
            self.version += 1
            return self.state()

    def approach(self, npc_id, *, expected_version=None):
        with self.lock:
            self.ready("private")
            if self.data["encounter"]:
                raise GameError("当前交涉还没有结束。")
            self.request_version(expected_version)
            if npc_id not in self.data["privateChats"] or not self.can_talk(self.data, npc_id):
                raise GameError("还没有找到可以交谈的本人。")
            loc = {"head_nurse": "station", "old_patient": "archive", "coworker": "power",
                   "sister": self.data["variant"]["sisterRoom"]}.get(npc_id, self.data["location"])
            self.open_encounter(encounter("talk", f"与{self.person(npc_id)['name']}交涉",
                self.person(npc_id)["public_profile"], npc_id,
                [option("finish", "结束交涉，回到现场", "这次交涉共过去30分钟。", op="finish")],
                source=npc_id, location=loc))
            self.version += 1
            return self.state()

    def act(self, action_id, *, confirm=False, expected_version=None):
        with self.lock:
            self.ready("act")
            action = next((a for a in self.case["actions"] if a["id"] == action_id), None)
            if action is None:
                raise GameError("这个行动不存在。", 400)
            self.request_version(expected_version)
            if action.get("dangerous"):
                if not confirm or expected_version is None:
                    raise GameError("请查看冒险提示，并确认当前状态后执行。")
            reasons = self.missing(action, self.data)
            if reasons:
                raise GameError("；".join(reasons))
            data = self.data
            op = action.get("operation")
            if op == "leave":
                f = data["flags"]
                ending = ("full" if all(f[k] for k in ("sisterRescued", "nameRecorded", "powerRestored", "debrisCleared"))
                          else "together" if f["sisterRescued"] else "solo")
                self.finish(ending, "机械门认出了编号工牌。你终于走回有街道的清晨。")
            else:
                location = (data["variant"]["sisterRoom"] if action_id in {"verify_sister", "rescue_sister"}
                            else action.get("location", data["location"]))
                event = action_scene(action_id, location)
                if event:
                    self.open_encounter(event)
                    if action_id == "follow_voice":
                        data["flags"]["followedVoice"] = True
                else:
                    data["location"] = location
                    self.apply_effects(action["effects"], private=True)
                    self.host(data, action["message"])
                    self.witness(action["message"])
                    self.tick()
            self.version += 1
            return self.state()

    def choose(self, event_id, choice_id, *, expected_version):
        with self.lock:
            # Choices are part of the current act, rather than a new phase action.
            super().ready("act")
            self.request_version(expected_version, required=True)
            event = self.data["encounter"]
            if not event or event["id"] != event_id:
                raise GameError("这个现场已经改变，请按当前现场行动。")
            item = next((c for c in event["choices"] if c["id"] == choice_id and c["id"] not in event["seen"]), None)
            if not item:
                raise GameError("这个现场选择不存在或已经执行。", 400)
            reasons = self.choice_reasons(item, self.data)
            if reasons:
                raise GameError("；".join(reasons))
            data = self.data
            if item["op"] == "inspect":
                ids = item["evidence"]
                self.apply_effects({"evidence": ids}, private=True)
                event["seen"].append(item["id"])
                materials = self.evidence(ids, data)
                event["log"].append({"text": item["text"], "evidenceIds": ids})
                for material in materials:
                    event["log"].append({"text": material["detail"], "evidenceIds": [material["id"]]})
                if "bracelet" in ids:
                    event["npcId"] = "sister"
                self.witness(item["text"], event["npcId"])
                data["lastAction"] = {"action": item["label"], "outcome": item["text"],
                                      "location": data["location"]}
                self.version += 1
                return self.state()
            if item["op"] == "execute":
                action = next(a for a in self.case["actions"] if a["id"] == event["source"])
                if action.get("operation") == "breaker":
                    if action["value"] != data["variant"]["breaker"]:
                        self.witness(f"许舟合上{action['value']}回路，安全灯未亮，广播尖叫，红线开始发热。", event["npcId"])
                        data["lastAction"] = {"action": item["label"], "outcome": "安全灯没有亮，红线开始发热，广播贴着耳膜尖叫。",
                                              "location": data["location"]}
                        self.open_encounter(threat("breaker", data["location"]))
                        self.version += 1
                        return self.state()
                    data["flags"]["powerRestored"] = True
                    self.host(data, "你合上回路。安全灯从配电房一路亮到病房，广播没有跟着响。")
                elif action.get("operation") == "verify":
                    data["flags"]["sisterVerified"] = True
                    self.host(data, "你把她亲口说出的童年回答与腕带、原始登记对上。床边的人是许宁。")
                else:
                    self.apply_effects(action["effects"], private=True)
                    self.host(data, item.get("text", action["message"]))
            elif item["op"] == "cancel":
                self.host(data, item.get("text", f"你从「{event['title']}」收手，行动没有完成。"))
            elif item["op"] == "finish":
                if event["kind"] == "search":
                    loc = next(l for l in self.locations if l["id"] == event["location"])
                    self.mark_searched(event)
                    self.host(data, f"你结束了{loc['name']}的调查，收好实际查看过的材料。")
                else:
                    self.host(data, f"你结束了与{self.person(event['npcId'])['name']}的交涉。")
            elif item["op"] == "escape":
                self.host(data, physical_outcome(event["source"], item["id"], data)
                          or f"「{event['title']}」：你选择{item['label']}。")
            outcome = physical_outcome(event["source"], item["id"], data) if item["op"] == "execute" else None
            if outcome:
                self.host(data, outcome)
            self.witness(f"{item['label']}。{outcome or ''}", event["npcId"])
            data["lastAction"] = {"action": item["label"],
                                  "outcome": outcome or data["board"][-1]["text"], "location": data["location"]}
            if item.get("shield"):
                data["flags"]["shield"] = False
            if item.get("retreat"):
                data["location"] = "station"
            self.apply_effects({"anomaly": item.get("anomaly", 0), "flags": item.get("flagsSet", {})})
            if item.get("anomaly"):
                self.host(data, f"这次接触留下{item['anomaly']}次异常，手腕的影子变得更深。")
            data["encounter"] = None
            # An unpaid scene costs one turn in total, however many objects or
            # dialogue exchanges it contained. Patrol interrupts a paid turn.
            turns = (0 if event.get("paid") else 1) + item.get("extra", 0)
            for _ in range(turns):
                self.tick(queue=False)
                if data["ending"]:
                    break
            if data["anomaly"] >= self.case["dungeon"]["anomalyLimit"] and not data["ending"]:
                self.finish("failure", "异常达到上限，门后的影子取代了你的脚步。")
            self.version += 1
            return self.state()

    def free_action(self, message, *, expected_version):
        if not isinstance(message, str) or not message.strip() or len(message) > 2000:
            raise GameError("写下你在现场要做的事，最多2000字。", 400)
        with self.lock:
            super().ready("act")
            self.request_version(expected_version, required=True)
            data, version = self.snapshot()
            intents = affordances(self, data)
            context = {
                "mode": "intent", "sessionId": data["sessionId"], "scriptId": self.case["id"],
                "yourCharacter": {"id": "scene_intent"},
                "lastResponseId": data["responses"].get("scene_intent"),
                "availableIntents": intents,
                "currentScene": self.public_encounter(data) or {
                    "location": data["location"], "description": SENSES[data["location"]][0]},
                "knownEvidence": self.evidence(data["hands"][data["player"]] | data["public"], data),
                "world": {k: v for k, v in self.world(data).items() if k != "flags"},
                "lastAction": data.get("lastAction"),
            }
        generated = self.generate(context, data["intentHistory"][-10:], message)
        result = validate_reply(deepcopy(generated), context)
        with self.lock:
            self.check_version(version)
            intent = next(i for i in intents if i["id"] == result["intentId"])
            id = intent["id"]
            event = self.data["encounter"]
            self.data["responses"]["scene_intent"] = generated.get("_responseId")
            self.data["intentHistory"].append({"question": message, "response": result["reply"]})
            del self.data["intentHistory"][:-20]
            if intent.get("reasons"):
                text = "你伸出手，又停住了。" + "；".join(intent["reasons"]) + "。眼前的人和物件还在原处。"
                self.scene_entry(text)
                self.witness(f"许舟尝试：{message}。实际没有完成，原因是{'；'.join(intent['reasons'])}。")
                self.version += 1
                return self.state()
            if id == "say":
                npc_id = person_here(self.data)
                if not npc_id:
                    self.scene_entry("你说完，只有扬声器底下的杂音回了一声。眼前还没有能核验的本人。")
                    self.version += 1
                    return self.state()
                # The private generator must run outside the engine lock.
                self.version += 1
                speech_version = self.version
            else:
                if id.startswith("choice:"):
                    self.choose(event["id"], id.split(":", 1)[1], expected_version=self.version)
                elif id.startswith("inspect:"):
                    self.open_encounter(self.investigation_for(self.data["location"]))
                    self.choose(self.data["encounter"]["id"], id.split(":", 1)[1], expected_version=self.version)
                elif id.startswith("nearby:"):
                    item = next(c for c in self.investigation_for(self.data["location"])["choices"]
                                if c["id"] == id.split(":", 1)[1])
                    event["choices"].append(deepcopy(item))
                    self.choose(event["id"], item["id"], expected_version=self.version)
                elif id.startswith("move:"):
                    target = id.split(":", 1)[1]
                    if event and target == self.data["location"]:
                        self.scene_entry("你就在这里。灯下的物件还没收好，眼前的事仍等着你处理。")
                    if event and target != self.data["location"]:
                        self.choose(event["id"], "finish", expected_version=self.version)
                    if not self.data["ending"] and not self.data["encounter"]:
                        self.open_encounter(self.investigation_for(target))
                    elif self.data["encounter"] and self.data["encounter"]["kind"] == "danger":
                        self.scene_entry("你还没走过岔口，白袖口已经挡在眼前。")
                elif id.startswith(("act:", "execute:")):
                    pieces = id.split(":")
                    if event:
                        # Merge a local investigation into its physical action;
                        # the final action still pays the scene's one turn.
                        old_log = event["log"]
                        if event["kind"] == "search":
                            self.mark_searched(event)
                        self.data["encounter"] = None
                    self.act(pieces[1], confirm=True, expected_version=self.version)
                    if event and self.data["encounter"]:
                        self.data["encounter"]["log"] = old_log + self.data["encounter"]["log"]
                    if pieces[0] == "execute" and self.data["encounter"]:
                        self.choose(self.data["encounter"]["id"], pieces[2], expected_version=self.version)
                elif id.startswith("talk:"):
                    if event:
                        self.choose(event["id"], "finish", expected_version=self.version)
                    if not self.data["ending"] and not self.data["encounter"]:
                        self.approach(id.split(":", 1)[1], expected_version=self.version)
                else:
                    self.physical_attempt(id, message, result["reply"])
                self.version += 1
                return self.state()
        return self.private(npc_id, message, expected_version=speech_version, enter_scene=True)

    def mark_searched(self, event):
        loc = next(l for l in self.locations if l["id"] == event["location"])
        required = ({"bracelet" if loc["id"] == self.data["variant"]["sisterRoom"] else "empty_bed"}
                    if loc["id"].startswith("ward") else set(loc["evidence"]))
        if required <= self.data["hands"][self.data["player"]] | self.data["public"]:
            if loc["id"] not in self.data["searched"]:
                self.data["searched"].append(loc["id"])

    def physical_attempt(self, id, message, feedback):
        data, event = self.data, self.data["encounter"]
        npc_id = person_here(data)
        if id in {"observe", "listen"}:
            key = "sensed:" + id
            text = SENSES[data["location"]][id == "listen"]
            if id == "observe":
                text += BODILY[min(data["anomaly"], len(BODILY) - 1)]
            if event and key in event["seen"]:
                text = "你又停下来确认了一遍。" + text
            elif event:
                event["seen"].append(key)
        elif id == "muffle":
            data["flags"]["lureActive"] = False
            text = "你捂住扬声器，拔掉眼前的播放线。杂音断了，走廊的声音骤然清楚。机械钟仍按自己的节奏走。"
        elif id in {"shout", "confront"}:
            if id == "confront":
                data["relationships"][npc_id] = max(-2, data["relationships"].get(npc_id, 0) - 1)
                flags = {"coworker": "workerHelping", "sister": "sisterReady"}
                if npc_id in flags:
                    data["flags"][flags[npc_id]] = False
                text = f"{self.person(npc_id)['name']}猛地挣开，收回了伸向你的手。金属撞击声顺走廊传开，你没有拿到东西。"
            else:
                text = "你的声音撞在瓷砖上，一层层传向走廊。远处的脚步立即停了，又开始朝这里靠近。"
            self.witness(f"{message}。{text}", npc_id)
            self.host(data, text)
            self.open_encounter(threat("patrol", data["location"]))
            # This is an unpaid disturbance, not a clock-scheduled patrol.
            data["encounter"]["paid"] = False
            data["encounter"]["npcId"] = npc_id
            self.cue(npc_id, f"你亲眼看见：{message}。{text}。巡查已经到门前。立即回应许舟。")
        elif id == "wait_here":
            text = "你留在原地，听着半小时从钟里走过去。"
            self.scene_entry(text)
            if event and event["kind"] == "search":
                self.mark_searched(event)
            data["encounter"] = None
            self.witness(message, npc_id)
            self.tick(queue=False)
        else:
            text = feedback
        if id not in {"shout", "confront", "wait_here"}:
            self.scene_entry(text)
            self.witness(f"许舟尝试：{message}。眼前的结果：{text}", npc_id)
        data["lastAction"] = {"action": message, "outcome": text, "location": data["location"]}

    def scene_turn(self, cue_id):
        with self.lock:
            super().ready("act")
            cue = self.data.get("sceneCue")
            if not cue or cue["id"] != cue_id:
                raise GameError("现场已经变化，对方会回应当前的事。")
            data, version = self.snapshot()
            npc_id = cue["npcId"]
            data["currentQuestion"] = ""
        generated = self.generate(self.context(data, npc_id, "private"), data["privateChats"][npc_id], cue["text"])
        with self.lock:
            self.check_version(version)
            reply, shared = self.commit_npc(npc_id, generated, True, prepared=data)
            action = next(a for a in self.npc_actions(data, npc_id) if a["id"] == reply["npcActionId"])
            label = action["label"] if action["id"] != "wait" else None
            event = self.data["encounter"]
            turns = self.data["privateChats"][npc_id]
            turns.append({"question": "", "response": reply["reply"], "evidenceIds": shared,
                          "presentedEvidenceIds": [], "actionLabel": label,
                          "encounterId": event["id"] if event else None, "spontaneous": True})
            self.scene_entry(reply["reply"], speaker_id=npc_id, action_label=label, evidence_ids=shared)
            if self.data.get("lastAction"):
                self.data["lastAction"]["response"] = {"npcId": npc_id, "text": reply["reply"]}
            self.data["sceneCue"] = None
            self.version += 1
            return {"reply": reply["reply"], "speakerId": npc_id,
                    "replyKey": f"{self.case['id']}:private-{npc_id}-{len(turns) - 1}", "state": self.state()}

    def silence(self, cue_id):
        with self.lock:
            cue = self.data.get("sceneCue")
            if cue and cue["id"] == cue_id:
                self.data["sceneCue"] = None
                self.version += 1
            return self.state()

    def npc_actions(self, data, npc_id):
        event = data["encounter"]
        return [a for a in self.person(npc_id)["npcActions"] if not self.missing(a, data, npc_id)
                and (a["id"] != "answer_memory" or (
                    event and event["source"] == "verify_sister" and event["npcId"] == npc_id
                    and data.get("currentQuestion", "").find("雨停了吗") >= 0))
                and (a["id"] != "steady" or data["flags"]["sisterVerified"])]

    def context(self, data, npc_id, mode):
        npc = self.person(npc_id)
        visible = data["public"] | data["hands"][npc_id]
        event = data["encounter"]
        return {
            "sessionId": data["sessionId"], "scriptId": self.case["id"],
            "lastResponseId": data["responses"].get(npc_id), "mode": "dungeon",
            "channel": mode,
            "caseBackground": {"title": self.case["title"], "summary": self.case["summary"],
                               "opening": self.case["opening"],
                               "people": [{k: p[k] for k in ("id", "name", "role")} for p in self.case["npcs"]]},
            "yourCharacter": {k: npc[k] for k in ("id", "name", "role", "private_secret", "facts", "strategy")},
            "yourGoals": self.books[npc_id]["goals"],
            "yourMemory": data["memories"].get(npc_id, ""),
            "yourEmotion": data["emotions"].get(npc_id, npc["initial_emotion"]),
            "currentEncounter": ({k: event[k] for k in ("kind", "title", "description", "location")}
                                 if event and event["npcId"] == npc_id else None),
            "presentedEvidence": self.evidence(data.get("presentedEvidence", []), data),
            "world": {**self.world(data), "flags": {
                key: value for key, value in data["flags"].items() if key in NPC_VISIBLE_FLAGS[npc_id]}},
            "witnessedActions": deepcopy(data.get("observations", {}).get(npc_id, [])),
            "relationship": data.get("relationships", {}).get(npc_id, 0),
            "rules": {"mode": self.case["mode"]["label"], "allowedActions": self.phase_config(data)["actions"],
                      "text": [r["text"] for r in self.case["dungeon"]["rules"]]},
            "publicDiscussion": [e for e in data["board"] if e["speakerId"] != "host"][-30:],
            "knownEvidence": self.evidence(visible, data),
            "publicEvidence": self.evidence(data["public"], data),
            "availableEvidence": self.evidence(data["hands"][npc_id] - data["public"], data),
            "availableNpcActions": [{k: a[k] for k in ("id", "label", "description") if k in a} for a in self.npc_actions(data, npc_id)],
        }

    def commit_npc(self, npc_id, generated, private, *, prepared=None):
        # Validate again at the commit boundary, including injected generators.
        prepared = self.data if prepared is None else prepared
        result = validate_reply(deepcopy(generated), self.context(prepared, npc_id, "private" if private else "public"))
        action = next(a for a in self.npc_actions(prepared, npc_id) if a["id"] == result["npcActionId"])
        if action["id"] == "answer_memory" and "伞还在槐树下" not in result["reply"]:
            raise GameError("她的回答还没有对上童年问答，本轮未保存。", 502)
        self.data["hands"][npc_id].update(prepared.get("presentedEvidence", []))
        shared = set(result["evidenceIds"]) & self.data["hands"][npc_id]
        shared.update(action["effects"].get("evidence", []))
        self.apply_effects({**action["effects"], "evidence": sorted(shared)}, private=private)
        self.data["memories"][npc_id] = result["memory"]
        self.data["responses"][npc_id] = result.get("_responseId")
        self.data["emotions"][npc_id] = result["emotion"]
        if not private:
            self.host(self.data, f"{self.person(npc_id)['name']}：{action['label']}。")
        return result, sorted(shared)

    def private(self, npc_id, message, *, evidence_ids=None, expected_version=None, enter_scene=False):
        if not message.strip() or len(message) > 2000:
            raise GameError("私聊内容不能为空，且最多2000字。", 400)
        with self.lock:
            self.ready("private")
            self.request_version(expected_version)
            if npc_id not in self.data["privateChats"]:
                raise GameError("请选择另一位角色私聊。", 400)
            event = self.data["encounter"]
            if event and event["npcId"] != npc_id:
                raise GameError("眼前的人还没有离开，不能同时找别人交谈。")
            if not self.can_talk(self.data, npc_id):
                raise GameError("还没有找到可以交谈的本人。")
            evidence_ids = [] if evidence_ids is None else evidence_ids
            owned = self.data["hands"][self.data["player"]] | self.data["public"]
            if (not isinstance(evidence_ids, list) or any(not isinstance(e, str) or e not in owned for e in evidence_ids)):
                raise GameError("只能出示你实际持有的材料。", 400)
            data, version = self.snapshot()
            if enter_scene and not event:
                data["encounter"] = encounter("talk", f"与{self.person(npc_id)['name']}交涉",
                    self.person(npc_id)["public_profile"], npc_id,
                    [option("finish", "结束交涉，回到现场", "这次交涉共过去30分钟。", op="finish")],
                    source=npc_id, location=data["location"])
            data["presentedEvidence"] = list(dict.fromkeys(evidence_ids))
            data["hands"][npc_id].update(data["presentedEvidence"])
            data["currentQuestion"] = message
        generated = self.generate(self.context(data, npc_id, "private"), data["privateChats"][npc_id], message)
        with self.lock:
            self.check_version(version)
            reply, shared = self.commit_npc(npc_id, generated, True, prepared=data)
            npc_action = next(a for a in self.npc_actions(data, npc_id) if a["id"] == reply["npcActionId"])
            label = npc_action["label"] if npc_action["id"] != "wait" else None
            if enter_scene and not event:
                self.open_encounter(data["encounter"])
                event = self.data["encounter"]
            self.data["privateChats"][npc_id].append({
                "question": message.strip(), "response": reply["reply"], "evidenceIds": shared,
                "presentedEvidenceIds": data["presentedEvidence"], "actionLabel": label,
                "encounterId": event["id"] if event else None})
            self.scene_entry(f"你：{message.strip()}")
            self.scene_entry(reply["reply"], speaker_id=npc_id,
                             action_label=label, evidence_ids=shared)
            self.data["sceneCue"] = None
            if not event:
                self.tick(queue=False)
            self.version += 1
            return {"reply": reply["reply"], "state": self.state()}

    def ai_turn(self):
        with self.lock:
            self.ready("act", pending_ok=True)
            if not self.data["pending"]:
                raise GameError("当前没有等待回应的角色。")
            data, version = self.snapshot()
            npc_id = data["pending"][0]
        generated = self.generate(self.context(data, npc_id, "public"), data["privateChats"][npc_id],
                                  "回应当前局势，按自己的利益选择一项可用行动。不要声称替玩家执行行动。")
        with self.lock:
            self.check_version(version)
            reply, shared = self.commit_npc(npc_id, generated, False)
            entry = {"id": len(self.data["board"]), "speakerId": npc_id,
                     "speakerName": self.person(npc_id)["name"], "text": reply["reply"],
                     "phase": 2, "evidenceIds": shared}
            self.data["board"].append(entry)
            self.data["pending"].pop(0)
            self.version += 1
            return {"reply": reply["reply"], "speakerId": npc_id,
                    "replyKey": f"{self.case['id']}:board-{entry['id']}", "state": self.state()}

    def result(self, data):
        titles = {"failure": "留在第七夜", "solo": "独自归来",
                  "together": "带她回家", "full": "把名字带出黑夜"}
        return {**data["ending"], "title": titles[data["ending"]["id"]],
                "truth": self.case["truth"], "variant": deepcopy(data["variant"]),
                "rules": deepcopy(self.case["dungeon"]["rules"]),
                "characters": [{k: n[k] for k in ("id", "name", "role", "private_secret", "facts")}
                               for n in self.case["npcs"]],
                "evidence": self.evidence([e["id"] for e in self.case["evidence"]], data)}
