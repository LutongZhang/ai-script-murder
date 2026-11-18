"""Deterministic engine checks. The fake generator does not verify model quality."""
from copy import deepcopy
import json
from threading import Event, Thread
import unittest

from backend.dungeon import DungeonGame
from backend.game import Game, GameError
from backend.npc_ai import AIError
from backend.scripts import load_scripts, validate_script


def reply(context, history, question):
    if context["yourCharacter"]["id"] == "sister" and "雨停了吗" in question:
        return {"reply": "阿舟，伞还在槐树下。你终于来了。", "memory": "哥哥问了童年问答。",
                "emotion": "松动", "evidenceIds": [], "npcActionId": "answer_memory"}
    return {"reply": "我先留在这里，你要仔细核对材料。", "memory": "正在观察。",
            "emotion": "戒备", "evidenceIds": [], "npcActionId": "wait"}


class DungeonChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scripts = load_scripts()

    def game(self, variant=0, generate=reply):
        g = DungeonGame(deepcopy(self.scripts["night_ward"]), generate)
        g.data["variant"] = deepcopy(g.case["dungeon"]["variants"][variant])
        g.start("temp_worker")
        g.advance()
        return g

    def step(self, g, operation, value):
        getattr(g, operation)(value)
        if operation == "search":
            objects = {"station": ["journal", "latch"], "archive": ["index", "name"],
                       "power": ["label", "fragments"], "exit": ["clock"],
                       "ward307": ["wrist"], "ward309": ["wrist"]}
            for obj in objects[value]:
                self.choose(g, obj)
            self.choose(g, "finish")
        elif g.data["encounter"]:
            if value == "verify_sister":
                g.private("sister", "雨停了吗？")
            self.choose(g, {"record_name": "write", "clear_fragment": "careful",
                            "retrieve_badge": "pry", "verify_sister": "confirm_identity",
                            "rescue_sister": "carry"}.get(value, "pull"))
            if g.data["encounter"] and g.data["encounter"]["source"] == "breaker":
                self.choose(g, "cut")
        if g.data["encounter"] and g.data["encounter"]["source"] == "patrol":
            self.choose(g, "shield" if g.data["flags"]["shield"] else "hide")
        while g.data["pending"]:
            g.ai_turn()

    def choose(self, g, choice_id):
        return g.choose(g.data["encounter"]["id"], choice_id, expected_version=g.version)

    def test_complete_fixed_path_both_layouts(self):
        for variant in (0, 1):
            with self.subTest(variant=variant):
                g = self.game(variant)
                for op, value in [("search", "archive"), ("act", "record_name"),
                                  ("search", "power"), ("act", "clear_fragment"),
                                  ("act", "switch_" + g.data["variant"]["breaker"].lower()),
                                  ("search", "station"), ("act", "retrieve_badge"),
                                  ("search", g.data["variant"]["sisterRoom"]),
                                  ("act", "verify_sister"), ("act", "rescue_sister")]:
                    self.step(g, op, value)
                self.assertEqual(g.data["turn"], 13)
                self.assertEqual(g.data["anomaly"], 0)
                result = g.act("leave")["result"]
                self.assertEqual(result["id"], "full")
                self.assertEqual(g.data["turn"], 13)

    def test_solo_and_together(self):
        for rescue in (False, True):
            g = self.game()
            for op, value in [("search", "station"), ("act", "retrieve_badge")]:
                self.step(g, op, value)
            if rescue:
                for op, value in [("search", "archive"), ("search", g.data["variant"]["sisterRoom"]),
                                  ("act", "verify_sister"), ("act", "rescue_sister")]:
                    self.step(g, op, value)
            while g.data["turn"] < 12:
                self.step(g, "act", "wait")
            self.assertEqual(g.act("leave")["result"]["id"], "together" if rescue else "solo")

    def test_risk_confirmation_and_upper_limit(self):
        g = self.game()
        before = deepcopy(g.data)
        with self.assertRaises(GameError):
            g.act("follow_voice")
        self.assertEqual(before, g.data)
        with self.assertRaises(GameError):
            g.act("follow_voice", confirm=True, expected_version=g.version - 1)
        for _ in range(3):
            g.act("follow_voice", confirm=True, expected_version=g.version)
            self.assertIsNone(g.state()["result"])
            self.choose(g, "shut")
            if g.data["pending"]:
                g.ai_turn()
        self.assertEqual(g.state()["result"]["id"], "failure")

    def test_patrol_and_shield(self):
        for shield, anomaly in ((False, 1), (True, 0)):
            g = self.game()
            for _ in range(5):
                self.step(g, "act", "wait")
            g.data["flags"]["shield"] = shield
            self.step(g, "search", "archive")
            self.assertEqual(g.data["anomaly"], anomaly)
            self.assertFalse(g.data["flags"]["shield"])

    def test_timeout_and_last_window(self):
        g = self.game()
        self.step(g, "search", "station")
        self.step(g, "act", "retrieve_badge")
        with self.assertRaises(GameError):
            g.act("leave")
        while g.data["turn"] < 15:
            self.step(g, "act", "wait")
        self.assertTrue(g.state()["world"]["exitOpen"])
        self.step(g, "act", "wait")
        self.assertEqual(g.state()["result"]["id"], "failure")
        with self.assertRaises(GameError):
            g.act("leave")

    def test_wrong_breaker_recoverable(self):
        g = self.game()
        self.step(g, "act", "switch_b")
        self.assertEqual(g.data["anomaly"], 1)
        self.step(g, "act", "switch_a")
        self.assertTrue(g.data["flags"]["powerRestored"])

    def test_repeat_and_missing_actions_no_cost(self):
        g = self.game()
        self.step(g, "search", "station")
        before = deepcopy(g.data)
        for op, value in (("search", "station"), ("act", "verify_sister"), ("act", "absent")):
            with self.assertRaises(GameError):
                getattr(g, op)(value)
            self.assertEqual(g.data, before)
        with self.assertRaises(GameError):
            g.advance()

    def test_dynamic_evidence_and_information_isolation(self):
        g = self.game(1)
        initial = json.dumps(g.state(), ensure_ascii=False)
        self.assertNotIn('"variant"', initial)
        self.assertNotIn("广播回声利用", initial)
        self.step(g, "search", "ward307")
        self.assertIn("empty_bed", g.data["hands"]["temp_worker"])
        self.step(g, "search", "archive")
        self.step(g, "search", "ward309")
        for npc in ("head_nurse", "old_patient", "coworker", "caller"):
            context = g.context(g.data, npc, "public")
            encoded = json.dumps(context, ensure_ascii=False)
            self.assertNotIn("伞还在槐树下", encoded)
            self.assertNotIn('"variant"', encoded)
            self.assertNotIn('"effects"', encoded)
            self.assertNotIn("腕带颜色：绿色", encoded)
        g.publish("bracelet")
        self.assertIn("腕带上写着许宁", json.dumps(g.context(g.data, "caller", "public"), ensure_ascii=False))
        self.assertNotIn("伞还在槐树下", json.dumps(g.context(g.data, "caller", "public"), ensure_ascii=False))

    def test_private_share_and_action(self):
        def cooperate(c, h, q):
            return {**reply(c, h, q), "npcActionId": "offer_badge"}
        g = self.game(generate=cooperate)
        g.private("head_nurse", "一起离开，好吗？")
        self.assertEqual(g.data["turn"], 1)
        self.assertIn("exit_badge", g.data["hands"]["temp_worker"])
        self.assertNotIn("exit_badge", g.data["public"])
        self.assertNotIn("一起离开", json.dumps(g.context(g.data, "caller", "public"), ensure_ascii=False))
        self.assertEqual(g.data["pending"], [])

    def test_ai_failure_scene_retry_does_not_repeat_cost(self):
        def fail(*args):
            raise AIError("故障")
        g = self.game(generate=fail)
        g.approach("head_nurse")
        before = deepcopy(g.data)
        with self.assertRaises(AIError):
            g.private("head_nurse", "让我看看柜钥匙。")
        self.assertEqual(g.data, before)
        with self.assertRaises(GameError):
            g.act("wait")
        g.generate = reply
        g.private("head_nurse", "为什么不肯开柜？")
        self.assertEqual(g.data["turn"], 0)
        self.choose(g, "finish")
        self.assertEqual(g.data["turn"], 1)

    def test_search_objects_and_partial_revisit(self):
        g = self.game()
        opened = g.search("archive")
        self.assertEqual(opened["world"]["turn"], 0)
        self.assertNotIn("roster", {e["id"] for e in opened["hand"]})
        self.choose(g, "index")
        self.assertIn("roster", g.data["hands"]["temp_worker"])
        self.assertNotIn("patient_name", g.data["hands"]["temp_worker"])
        self.assertEqual(g.data["turn"], 0)
        self.choose(g, "finish")
        self.assertNotIn("archive", g.data["searched"])
        g.search("archive")
        self.choose(g, "name")
        self.choose(g, "finish")
        self.assertIn("archive", g.data["searched"])
        self.assertEqual(g.data["turn"], 2)

    def test_scene_choices_version_replay_and_navigation(self):
        g = self.game()
        opened = g.search("station")
        event_id, old_version = opened["encounter"]["id"], opened["version"]
        self.choose(g, "journal")
        before = deepcopy(g.data)
        for command in (
            lambda: g.choose(event_id, "latch", expected_version=old_version),
            lambda: g.choose(event_id, "journal", expected_version=g.version),
            lambda: g.choose("stale", "finish", expected_version=g.version),
            lambda: g.act("wait"),
            lambda: g.search("archive"),
            lambda: g.private("coworker", "来这里"),
        ):
            with self.assertRaises(GameError):
                command()
            self.assertEqual(g.data, before)
        self.choose(g, "finish")
        before = deepcopy(g.data)
        with self.assertRaises(GameError):
            g.choose(event_id, "finish", expected_version=g.version)
        self.assertEqual(g.data, before)

    def test_negotiation_unblocks_cabinet_without_extra_time(self):
        def negotiate(c, h, q):
            if c["presentedEvidence"] and h:
                return {**reply(c, h, q), "reply": "先救人。钥匙给你，开柜吧。",
                        "npcActionId": "open_cabinet"}
            return reply(c, h, q)
        g = self.game(generate=negotiate)
        self.step(g, "search", "station")
        g.act("retrieve_badge")
        with self.assertRaises(GameError):
            self.choose(g, "unlock")
        g.private("head_nurse", "我要带病人出去，请把钥匙给我。")
        self.assertFalse(g.data["flags"]["cabinetUnlocked"])
        g.private("head_nurse", "日志我先保留，我们先救人。", evidence_ids=["nurse_log"])
        self.assertTrue(g.data["flags"]["cabinetUnlocked"])
        self.assertEqual(g.data["turn"], 1)
        self.choose(g, "unlock")
        self.assertEqual(g.data["turn"], 2)
        self.assertIn("exit_badge", g.data["hands"]["temp_worker"])

    def test_private_presentation_is_atomic_and_stays_with_recipient(self):
        seen = []
        def observe(c, h, q):
            seen.append(c)
            return reply(c, h, q)
        g = self.game(generate=observe)
        self.step(g, "search", "station")
        g.approach("head_nurse")
        g.private("head_nurse", "这本日志你怎么解释？", evidence_ids=["nurse_log"])
        self.assertEqual(seen[0]["presentedEvidence"][0]["id"], "nurse_log")
        self.assertIn("nurse_log", g.data["hands"]["head_nurse"])
        self.assertNotIn("nurse_log", g.data["public"])
        caller = json.dumps(g.context(g.data, "caller", "public"), ensure_ascii=False)
        self.assertNotIn("留有压痕的护理日志", caller)
        self.assertNotIn("这本日志你怎么解释", caller)
        before = deepcopy(g.data)
        for ids in (["roster"], "nurse_log", [None]):
            with self.assertRaises(GameError):
                g.private("head_nurse", "看看这个。", evidence_ids=ids)
            self.assertEqual(g.data, before)
        g.generate = lambda c, h, q: {**reply(c, h, q), "npcActionId": "invent"}
        with self.assertRaises(AIError):
            g.private("head_nurse", "这是我的招聘页。", evidence_ids=["recruitment"])
        self.assertEqual(g.data, before)
        self.assertNotIn("recruitment", g.data["hands"]["head_nurse"])

    def test_worker_help_changes_cleanup_time(self):
        for help, expected in ((False, 3), (True, 2)):
            g = self.game(generate=lambda c, h, q: {
                **reply(c, h, q), "npcActionId": "help", "reply": "我来压住箱盖，你用夹钳。"})
            self.step(g, "search", "power")
            g.act("clear_fragment")
            if help:
                g.private("coworker", "一起封装残片，我不会把你丢下。")
            self.choose(g, "together" if help else "careful")
            self.assertTrue(g.data["flags"]["debrisCleared"])
            self.assertEqual(g.data["turn"], expected)
            self.assertEqual(g.data["anomaly"], 0)

    def test_sister_requires_live_memory_answer_and_reassurance(self):
        g = self.game()
        with self.assertRaises(GameError):
            g.approach("sister")
        self.step(g, "search", "archive")
        self.step(g, "search", g.data["variant"]["sisterRoom"])
        self.assertNotIn("伞还在槐树下", g.evidence(["bracelet"])[0]["detail"])
        g.act("verify_sister")
        before = deepcopy(g.data)
        with self.assertRaises(GameError):
            self.choose(g, "confirm_identity")
        self.assertEqual(g.data, before)
        g.private("sister", "你是谁？")
        self.assertFalse(g.data["flags"]["memoryConfirmed"])
        g.private("sister", "雨停了吗？")
        self.assertEqual(g.data["turn"], 2)
        self.choose(g, "confirm_identity")
        g.act("rescue_sister")
        with self.assertRaises(GameError):
            self.choose(g, "walk")
        g.generate = lambda c, h, q: {**reply(c, h, q), "reply": "阿舟，我跟你走。",
                                      "npcActionId": "steady"}
        g.private("sister", "我就在你身旁，握住我的手。")
        self.choose(g, "walk")
        self.assertTrue(g.data["flags"]["sisterRescued"])
        self.assertEqual(g.data["turn"], 4)
        self.assertNotIn("伞还在槐树下", json.dumps(g.context(g.data, "caller", "public"), ensure_ascii=False))

    def test_incorrect_ai_memory_response_cannot_verify(self):
        g = self.game(generate=lambda c, h, q: {
            **reply(c, h, q), "reply": "我不记得了。", "npcActionId": "answer_memory"})
        self.step(g, "search", "archive")
        self.step(g, "search", g.data["variant"]["sisterRoom"])
        g.act("verify_sister")
        before = deepcopy(g.data)
        with self.assertRaises(GameError):
            g.private("sister", "雨停了吗？")
        self.assertEqual(g.data, before)

    def test_violation_escape_choices_change_consequences(self):
        for action, choice, anomaly, location in (
            ("follow_voice", "shut", 1, "station"),
            ("follow_voice", "deeper", 2, "ward309"),
            ("force_gate", "mark", 1, "station"),
            ("force_gate", "pursue", 2, "exit"),
        ):
            g = self.game()
            g.act(action, confirm=True, expected_version=g.version)
            self.assertEqual(g.data["anomaly"], 0)
            self.assertEqual(g.data["encounter"]["kind"], "danger")
            self.choose(g, choice)
            self.assertEqual(g.data["anomaly"], anomaly)
            self.assertEqual(g.data["location"], location)
            self.assertEqual(g.data["turn"], 1)

    def test_wrong_breaker_can_be_corrected_in_same_encounter(self):
        g = self.game()
        self.step(g, "search", "power")
        g.act("switch_b")
        self.choose(g, "pull")
        self.assertEqual(g.data["encounter"]["source"], "breaker")
        self.assertEqual(g.data["turn"], 1)
        self.choose(g, "reroute")
        self.assertTrue(g.data["flags"]["powerRestored"])
        self.assertEqual(g.data["anomaly"], 1)
        self.assertEqual(g.data["turn"], 2)

    def test_patrol_retreat_cost_and_optional_shield_consumption(self):
        for response, expected_turn, shield_left in (("retreat", 7, True), ("shield", 6, False)):
            g = self.game()
            for _ in range(5):
                self.step(g, "act", "wait")
            g.data["flags"]["shield"] = True
            g.search("archive")
            self.choose(g, "index")
            self.choose(g, "name")
            self.choose(g, "finish")
            self.assertEqual(g.data["encounter"]["source"], "patrol")
            self.assertEqual(g.data["turn"], 6)
            self.assertEqual(g.data["anomaly"], 0)
            self.choose(g, response)
            self.assertEqual(g.data["turn"], expected_turn)
            self.assertEqual(g.data["anomaly"], 0)
            self.assertEqual(g.data["flags"]["shield"], shield_left)

    def test_cancel_and_deadline_do_not_complete_objective(self):
        g = self.game()
        self.step(g, "search", "archive")
        g.act("record_name")
        self.choose(g, "cancel")
        self.assertFalse(g.data["flags"]["nameRecorded"])
        while g.data["turn"] < 15:
            self.step(g, "act", "wait")
        g.act("record_name")
        self.choose(g, "cancel")
        self.assertEqual(g.state()["result"]["id"], "failure")
        self.assertIsNone(g.state()["encounter"])

    def test_private_failure_and_invalid_generation_atomic(self):
        for change in ({"npcActionId": "invent"}, {"evidenceIds": ["roster"]}):
            g = self.game(generate=lambda c, h, q: {**reply(c, h, q), **change})
            before = deepcopy(g.data)
            with self.assertRaises(AIError):
                g.private("head_nurse", "你好")
            self.assertEqual(g.data, before)

    def test_reset_rejects_stale_generation(self):
        entered, release = Event(), Event()
        errors = []
        def slow(c, h, q):
            entered.set()
            release.wait(5)
            return reply(c, h, q)
        g = self.game(generate=slow)
        def run():
            try:
                g.private("head_nurse", "你好")
            except GameError as exc:
                errors.append(exc.status)
        thread = Thread(target=run)
        thread.start()
        self.assertTrue(entered.wait(5))
        g.reset()
        release.set()
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [409])
        self.assertIsNone(g.data["player"])

    def test_bad_configs_rejected(self):
        for mutate in (
            lambda s: s["actions"][0]["effects"]["flags"].update(unknown=True),
            lambda s: s["dungeon"]["variants"][0].update(breaker="C"),
            lambda s: s["npcs"][1]["npcActions"][1]["effects"].update(evidence=["roster"]),
            lambda s: s["dungeon"].update(dawnAt=16),
            lambda s: s["evidence"][0].update(detail="{private_secret}"),
        ):
            s = deepcopy(self.scripts["night_ward"])
            mutate(s)
            with self.assertRaises(ValueError):
                validate_script(s)

    def test_original_games_smoke(self):
        for script in self.scripts.values():
            if script.get("gameType") != "dungeon" and script["availability"]["status"] == "ready":
                g = Game(deepcopy(script), reply)
                g.start(script["npcs"][0]["id"])
                state = g.advance()
                self.assertEqual(state["case"]["gameType"], "murder")
                self.assertIsNone(state["result"])
                c = g.context(g.data, script["npcs"][1]["id"], "private")
                self.assertEqual(c["mode"], "private")


if __name__ == "__main__":
    unittest.main()
