import { ART } from "./dungeonArt.js";

export const SCENES = {
  station: {
    image: ART.station,
    description: "台灯照着摊开的交班册。走廊深处，脚步声停了又响。",
    object: "交班台", search: "翻查护理日志与备用柜",
    point: [36, 47], sound: "荧光灯的低鸣 · 远处脚步",
    evidence: ["nurse_log", "safe_corner", "exit_badge", "patient_name"],
  },
  archive: {
    image: ART.archive,
    description: "纸页在指间发脆。红笔覆盖的记录下面，还有一份原始登记。",
    object: "原始病案", search: "翻找许宁的转床登记",
    point: [39, 48], sound: "纸张摩擦 · 门外拖步",
    evidence: ["roster", "patient_name"],
  },
  power: {
    image: ART.power,
    description: "两只开关并排立着，纸标签轻轻颤动。角落里的残片似乎还在发热。",
    object: "接线柜", search: "检查接线标签与角落残片",
    point: [46, 38], sound: "电流杂音 · 管道回响",
    evidence: ["maintenance", "fragment_report"],
  },
  ward307: {
    image: ART.ward307,
    description: "床帘半掩着。呼吸声从白色被单后传来，你还不能确定那是谁。",
    object: "床边腕带", search: "靠近病床，检查腕带",
    point: [53, 46], sound: "缓慢呼吸 · 窗框轻响",
    evidence: ["bracelet", "empty_bed"],
  },
  ward309: {
    image: ART.ward309,
    description: "门牌没有变，床帘后的轮廓却让你迟疑。熟悉的声音不能代替核验。",
    object: "床边腕带", search: "靠近病床，检查腕带",
    point: [34, 45], sound: "床帘摩擦 · 断续呼吸",
    evidence: ["bracelet", "empty_bed"],
  },
  exit: {
    image: ART.exit,
    description: "消防门后没有街道。门边的机械钟，仍按自己的节奏走动。",
    object: "机械门铭牌", search: "查看机械钟与出口铭牌",
    point: [50, 41], sound: "机械钟滴答 · 风穿门缝",
    evidence: ["exit_notice", "exit_badge"],
  },
};

export const CHARACTERS = {
  patrol: { image: ART.patrol },
  head_nurse: { image: ART.head_nurse },
  old_patient: { image: ART.old_patient },
  coworker: { image: ART.coworker },
  // The caller has no verified human appearance.
  caller: { image: ART.caller },
  sister: { image: ART.sister },
};

export function sceneActions(state, locationId) {
  const clues = [...state.publicEvidence, ...state.hand];
  const knownRoom = clues.find(item => item.id === "roster")?.summary.match(/(307|309)/)?.[1];
  return state.actions.filter(item => {
    if (item.reasons.includes("已经完成") || item.reasons.includes("已取得材料")) return false;
    if (["verify_sister", "rescue_sister"].includes(item.id)) {
      return locationId === `ward${knownRoom}` && clues.some(item => item.id === "bracelet");
    }
    if (item.id === "leave") return locationId === "exit";
    return item.location === locationId;
  });
}

export function sceneDescription(state) {
  const { world } = state;
  const knownRoom = [...state.publicEvidence, ...state.hand].find(item => item.id === "roster")?.summary.match(/(307|309)/)?.[1];
  if (world.location === "exit" && world.exitOpen) return "门锁发出一声轻响。05:00的出口窗口已经开启，门后终于透进清晨的光。";
  if (world.location.startsWith("ward") && world.flags.sisterVerified
      && (world.location === `ward${knownRoom}` || world.flags.sisterRescued)) {
    return world.flags.sisterRescued ? "许宁跟在你身旁。接下来，你要找到回家的出口。" : "登记、腕带和你们的童年问答终于对上了。床边的人是许宁。";
  }
  if (world.location === "power" && world.flags.powerRestored) return "安全灯重新亮起来。角落里的残片是否清干净，决定灯光能不能保护你。";
  return SCENES[world.location].description;
}
