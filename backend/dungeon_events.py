"""Authored hospital encounters. Only the engine commits their consequences."""


def option(id, label, detail="", **values):
    return {"id": id, "label": label, "detail": detail, **values}


def encounter(kind, title, description, npc, choices, **values):
    return {"kind": kind, "title": title, "description": description,
            "npcId": npc, "choices": choices, "log": [], "seen": [], **values}


def investigation(location, sister_room):
    end = option("finish", "留在原地收好材料，结束调查", "本次调查共过去30分钟；不会移动到别处。", op="finish")
    scenes = {
        "station": ("交班台上的红笔", "沈青按住交班册，视线在你和备用柜之间移动。台灯下有一本红笔日志，门后还留着加固痕迹。", "head_nurse", [
            option("journal", "侧着灯光，翻看日志背页", op="inspect", evidence=["nurse_log"],
                   text="你把纸页对着台灯，压痕露出沈青的签名。她的手停在半空，没有再替你翻页。"),
            option("latch", "蹲下检查门闩与旧划痕", op="inspect", evidence=["safe_corner"],
                   text="门闩内侧有两道撞痕，外侧的木头却没有裂。有人确实在这里挡住过巡查。")]),
        "archive": ("没有被涂掉的那一页", "周槐坐在档案柜旁，一遍遍描着自己的名字。柜里有转床索引，也有被红笔划掉姓名的旧病案。", "old_patient", [
            option("index", "按许宁的名字逐页查转床索引", op="inspect", evidence=["roster"],
                   text="你顺着原始病案号找到一页转床登记。红笔只改过抄本，这一页还在。"),
            option("name", "抬起涂黑的旧病案，辨认压痕", op="inspect", evidence=["patient_name"],
                   text="涂黑的栏位下压着“周槐，0719”。老人把手指按在那两个字旁，像怕它们再跑掉。")]),
        "power": ("接线柜与会动的残片", "陆闻握着螺丝刀站在回路旁。标签被折进柜缝，角落的隔离箱下面传来刮擦声。", "coworker", [
            option("label", "拉出折进柜缝的本轮标签", op="inspect", evidence=["maintenance"],
                   text="你展平这一轮的接线标签。陆闻指了指上面的日期：旧轮班的接法不能照搬。"),
            option("fragments", "用灯照隔离箱下面的残片", op="inspect", evidence=["fragment_report"],
                   text="灯亮起时，残片转向你。箱盖内贴着旧护工留下的处理记录，纸角已经焦黑。")]),
        "exit": ("门锁不听广播", "扬声器说门已经开了，门边机械钟却仍在走。消防门的缝隙里传来一阵和走廊相同的风。", "caller", [
            option("clock", "贴近机械钟，读铭牌与刷卡槽", op="inspect", evidence=["exit_notice"],
                   text="你擦掉铭牌上的灰，看清独立机械钟的开窗时刻。扬声器的声音压不住齿轮的滴答。")]),
    }
    if location.startswith("ward"):
        return encounter("search", "床帘后的人", "你站在床尾。床帘后传来呼吸，门边扬声器同时叫着你的全名。先看清眼前的东西，再决定相信谁。",
                         None, [
            option("wrist", "掀开床帘，查看床边腕带", op="inspect",
                   evidence=["bracelet" if location == sister_room else "empty_bed"],
                   text="你拉开床帘，让手电停在床边。"),
            end], location=location, source=location)
    title, description, npc, choices = scenes[location]
    return encounter("search", title, description, npc, [*choices, end], location=location, source=location)


def action_scene(action, location, flags=None):
    cancel = option("cancel", "收手，退出现场", "已经花去30分钟，没有完成这项行动。", op="cancel")
    scenes = {
        "record_name": ("落笔之前", "交班册的空栏正在变淡。沈青把红笔横在纸上，周槐的旧病案号握在你手里。", "head_nurse", [
            option("write", "照原始病案写下“周槐，0719”", op="execute",
                   text="你移开红笔，把姓名与病案号一笔一画写进交班册。那一行终于不再褪色。"),
            option("discharge", "顺着红笔，替他填“已经出院”", "会保留抹名状态。", op="cancel",
                   text="你填了出院栏，却没有恢复实名。纸上的“无名患者”仍然没有变。")]),
        "clear_fragment": ("隔离箱的箱盖", "残片在箱下翻动。箱盖很重，一个人慢慢封装会耽误时间；陆闻可以帮你压住箱盖，但他要先决定是否信任你。", "coworker", [
            option("together", "让陆闻压住箱盖，用夹钳封装", "需要他在交涉中答应帮忙。", op="execute", flags=["workerHelping"]),
            option("careful", "独自用夹钳逐片封装", "额外过去30分钟。", op="execute", extra=1),
            option("bare", "直接伸手，把残片塞进箱里", "残片可能附着到身上。", op="execute", anomaly=1, dangerous=True,
                   text="你抓住最后一片时，它贴住了你的手腕。箱子封好了，皮下却多出一道不随手臂转动的影子。")]),
        "retrieve_badge": ("沈青手里的柜钥匙", "备用柜有钢印封条。沈青把钥匙攥在掌心，没有立刻让开。你可以拿日志和她交涉，也可以动手拆柜门。", "head_nurse", [
            option("unlock", "用沈青交出的钥匙打开备用柜", "需要她答应开柜。", op="execute", flags=["cabinetUnlocked"]),
            option("pry", "从铰链侧慢慢拆下柜门", "额外过去30分钟，保留工牌。", op="execute", extra=1),
            option("smash", "砸开柜门，抓起工牌", "撞击声会留下异常。", op="execute", anomaly=1, dangerous=True)]),
        "verify_sister": ("你们两个人才知道的问答",
            "腕带和原始登记已经放在床边。" + (
                "她已亲口答对童年问答，你可以将已得到的回答与两份材料逐项核对，无需再问。"
                if (flags or {}).get("memoryConfirmed") else "女孩盯着你，像在等一句只有你们懂的话。"
            ) + "广播的声音在门外停了下来。", "sister", [
            option("confirm_identity", "把她的回答与登记、腕带逐项核对",
                   "她的回答已确认，可直接与原始登记、床边腕带核对三项；核验不会自动安抚或带她离床。"
                   if (flags or {}).get("memoryConfirmed") else "先在交谈中问出你们的童年问答。",
                   op="execute", flags=["memoryConfirmed"])]),
        "rescue_sister": ("她不肯松开的床栏", "许宁确认了你，却仍抓着床栏。她的腿发软，害怕站起来后你又不见了。你可以先和她说话，也可以扶着她慢慢走。", "sister", [
            option("walk", "握住她的手，让她跟着你的步子走", "需要先让她在交谈中安定下来。", op="execute", flags=["sisterReady"]),
            option("carry", "扶住她，慢慢把她带出病床", "额外过去30分钟。", op="execute", extra=1),
            option("pull", "趁脚步接近，把她强拉出床边", "慌乱会留下异常。", op="execute", anomaly=1, dangerous=True)]),
        "follow_voice": ("门里的声音忽然贴近了", "你循声打开门。门后没有人，只有一台录音机。你的全名从身后响起，门把手正在自己转动。", "caller", [
            option("shut", "压住门把手，倒退着关门", "留下这次开门造成的一次异常。", op="escape", anomaly=1, retreat=True),
            option("shield", "用陆闻的护栏挡住伸来的影子", "消耗护栏，仍留下开门异常。", op="escape", anomaly=1, shield=True),
            option("deeper", "继续往里走，追上那个声音", "影子将更深地附着。", op="escape", anomaly=2, dangerous=True)]),
        "force_gate": ("第二段走廊", "你推开消防门，面前仍是同一段走廊。第二扇门也被推开了，里面有一个与你同时抬手的人。", "caller", [
            option("mark", "在门边留下划痕，沿原路退回", "留下闯门异常，回到护士站。", op="escape", anomaly=1, retreat=True),
            option("pursue", "冲过去，撞开里面的第二扇门", "重复走廊会吞掉更多影子。", op="escape", anomaly=2, dangerous=True)]),
    }
    if action.startswith("switch_"):
        return encounter("action", "合闸前的一瞬", "两只开关的金属柄冰冷。陆闻退开一步，让你自己决定；你可以在落闸前继续核对标签或问他。",
                         "coworker", [option("pull", f"握紧手柄，合上{action[-1].upper()}回路", op="execute"), cancel],
                         source=action, location=location)
    if action not in scenes:
        return None
    title, description, npc, choices = scenes[action]
    kind = "danger" if action in {"follow_voice", "force_gate"} else "action"
    return encounter(kind, title, description, npc, choices if kind == "danger" else [*choices, cancel],
                     source=action, location=location)


def threat(kind, location, flags=None):
    if kind == "breaker":
        return encounter("danger", "广播回路反咬了你", "你刚合闸，安全灯没亮，广播却贴着耳膜尖叫。柜里的红线开始发热，走廊脚步正在转向这里。",
                         "coworker", [
            option("cut", "立即断开刚合上的回路", "留下一次异常；供电仍未恢复。", op="escape", anomaly=1),
            option("reroute", "照已读标签切到安全灯回路", "留下一次异常，同时纠正供电。", op="escape",
                   evidenceRequired=["maintenance"], flagsSet={"powerRestored": True}, anomaly=1),
            option("freeze", "按住开关，等广播自己停下来", "发热回路会留下更多异常。", op="escape", anomaly=2, dangerous=True)],
                         source="breaker", location=location)
    cover = {"station": "缩到交班台下", "archive": "贴着档案柜后", "power": "贴着接线柜后", "exit": "缩进门框阴影里"}.get(location, "贴着床底")
    flags = flags or {}
    description = "门边的灯闪了一下。门缝先出现一截白袖口，再出现一只没有指纹的手。"
    description += ("残片已经封进隔离箱，但它仍在推门。"
                    if flags.get("debrisCleared") else "它沿地上的碎片转向你，已经开始推门。")
    description += "安全灯供电已经恢复。" if flags.get("powerRestored") else "安全灯供电仍未恢复。"
    hide_detail = ("巡查已经推门，屏息仍会留下接触造成的一次异常。"
                   if flags.get("debrisCleared") else "残片仍会暴露位置，留下一次异常。")
    choices = [
        *([option("latch", "压住护士站门板，把门闩推到底", "门闩仍然能挡住它。", op="escape")] if location == "station" else []),
    ]
    return encounter("danger", "脚步停在你的门外", description,
                     "coworker", [
        *choices,
        option("retreat", "放下手里的事，退回护士站插上门闩", "额外过去30分钟。", op="escape", retreat=True, extra=1),
        option("shield", "用陆闻加固的护栏抵住门", "消耗一次性护栏。", op="escape", shield=True),
        option("lure", "把正在播放的广播引向空走廊", "需要广播正在诱导，随后会切断它。", op="escape", flags=["lureActive"],
               flagsSet={"lureActive": False}),
        option("hide", f"{cover}屏住呼吸，等它离开", hide_detail, op="escape", anomaly=1),
        option("fight", "挥起工具，迎着白袖口撞出去", "近身接触会留下两次异常。", op="escape", anomaly=2, dangerous=True)],
                     source="patrol", location=location, paid=True)
