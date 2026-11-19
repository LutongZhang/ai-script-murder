import { useEffect, useRef, useState } from "react";
import { DungeonConversation } from "./DungeonConversation.jsx";
import { sceneDescription } from "../hooks/dungeonScene.js";

function passages(text) {
  const result = [];
  for (const paragraph of String(text || "").split(/\n+/).filter(part => part.trim())) {
    let remaining = [...paragraph];
    while (remaining.length > 145) {
      const first = remaining.slice(0, 145).join("");
      const punctuation = Math.max(...["。", "！", "？", "；", "，"].map(mark => first.lastIndexOf(mark)));
      const length = punctuation >= 70 ? [...first.slice(0, punctuation + 1)].length : 145;
      result.push(remaining.splice(0, length).join(""));
    }
    if (remaining.length) result.push(remaining.join(""));
  }
  return result;
}

function story(state, npc) {
  const entries = [];
  const add = (id, text, speakerId = null, name = "旁白", note = "") => {
    passages(text).forEach((part, index) => entries.push({ id: `${id}:${index}:${part}`, text: part, speakerId, name, note }));
  };
  if (state.phaseKind === "reading") {
    add("opening", "妹妹已经三天没有回家。你穿上临时护工的制服，混进永昼病院的夜班。");
    add("opening-door", "你推开护士站的门。台灯下摆着交班册，走廊深处响起脚步声。回头看时，电梯后的楼梯已经消失了。");
    return entries;
  }
  const event = state.encounter;
  if (event) {
    add(`${event.id}:description`, event.description, null, "旁白", event.title);
    if (state.world.anomaly > 0 && event.kind === "danger") add(`body:${state.world.anomaly}`, state.body);
    event.log.forEach((entry, index) => {
      const player = !entry.speakerId && entry.text.startsWith("你：");
      add(`${event.id}:log:${index}`, player ? entry.text.slice(2) : entry.text,
        player ? state.player.id : entry.speakerId, player ? "许舟" : entry.speakerName || "旁白", entry.actionLabel);
    });
  } else {
    const outcome = state.lastAction?.location === state.world.location ? state.lastAction.outcome : null;
    add(`scene:${state.world.location}:${outcome || sceneDescription(state)}`, outcome || sceneDescription(state));
    if (state.world.anomaly > 0) add(`body:${state.world.anomaly}`, state.body);
    if (state.lastAction?.intentFeedback && state.lastAction.location === state.world.location) {
      add(`intent:${state.lastAction.intentFeedback}`, state.lastAction.intentFeedback);
    }
    const turns = state.privateChats[npc?.id] || [];
    const latest = turns.at(-1);
    if (latest) {
      if (latest.question) add(`private:${npc.id}:${turns.length}:question`, latest.question, state.player.id, "许舟");
      add(`private:${npc.id}:${turns.length}:reply`, latest.response, npc.id, npc.name, latest.actionLabel);
    } else if (state.lastAction?.response) {
      const response = state.lastAction.response;
      add(`response:${response.npcId}:${response.text}`, response.text, response.npcId,
        state.npcs.find(person => person.id === response.npcId)?.name || "传来的声音");
    }
  }
  if (state.result) add(`ending:${state.result.id}`, state.result.reason, null, "旁白", state.result.title);
  return entries;
}

export function DungeonNovel({ game, narration, npc, location, scene, actions, onExecute, onSearch, onMap,
  onBook, onLog, onSpeaker }) {
  const { state, busy, action } = game;
  const event = state.encounter;
  const reading = state.phaseKind === "reading";
  const group = `${state.case.id}:${state.phaseKind}:${event?.id || state.world.location}`;
  const frames = story(state, npc);
  const signature = frames.map(frame => frame.id).join("\0");
  const [position, setPosition] = useState(0);
  const [visible, setVisible] = useState(0);
  const [composer, setComposer] = useState(false);
  const [people, setPeople] = useState(false);
  const drawer = useRef(null);
  const moreMenu = useRef(null);
  const composerTrigger = useRef(null);
  const typingTimer = useRef(null);
  const previous = useRef({ group, ids: frames.map(frame => frame.id) });
  const current = frames[Math.min(position, frames.length - 1)];
  const typing = Boolean(current && visible < current.text.length);
  const complete = position >= frames.length - 1 && !typing;
  const locked = Boolean(busy) || state.pendingSpeakers.length > 0;
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => {
    const old = previous.current;
    const ids = frames.map(frame => frame.id);
    if (old.group !== group) {
      setPosition(0);
      setComposer(false);
      setPeople(false);
      if (moreMenu.current) moreMenu.current.open = false;
    } else if (ids.length) {
      const index = ids.indexOf(old.ids[position]);
      if (index === -1) setPosition(0);
      else if (ids.length > old.ids.length && position === old.ids.length - 1 && !typing) setPosition(old.ids.length);
      else if (index !== position) setPosition(index);
    }
    previous.current = { group, ids };
  }, [group, signature]);

  useEffect(() => {
    setVisible(reducedMotion ? current?.text.length || 0 : 0);
    if (!current || reducedMotion) return;
    let count = 0;
    const timer = window.setInterval(() => {
      count = Math.min(count + 2, current.text.length);
      setVisible(count);
      if (count === current.text.length) window.clearInterval(timer);
    }, 25);
    typingTimer.current = timer;
    return () => window.clearInterval(timer);
  }, [current?.id, reducedMotion]);

  useEffect(() => {
    if (!composer) return;
    const previousFocus = composerTrigger.current || document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const input = drawer.current?.querySelector("textarea:not(:disabled)");
    (input || drawer.current)?.focus();
    return () => { document.body.style.overflow = overflow; previousFocus?.focus(); };
  }, [composer]);

  useEffect(() => {
    onSpeaker(state.npcs.some(person => person.id === current?.speakerId) ? current.speakerId : null);
  }, [current?.id, current?.speakerId]);

  function next() {
    if (typing) { window.clearInterval(typingTimer.current); setVisible(current.text.length); }
    else if (position < frames.length - 1) setPosition(old => old + 1);
  }

  function openComposer(mode, trigger) {
    composerTrigger.current = mode === "action" ? moreMenu.current?.querySelector("summary") : trigger;
    if (moreMenu.current) {
      moreMenu.current.open = false;
    }
    setComposer(mode);
  }

  const choices = event ? event.choices.map(item => ({ ...item, select: () => action("choice", {
    encounterId: event.id, choiceId: item.id, version: state.version,
  }) })) : [
    ...(!location.searched ? [{
      id: "inspect", label: scene.search, available: location.available, detail: "进入调查现场", reasons: [],
      select: () => onSearch(location.id),
    }] : []),
    ...actions.map(item => ({ ...item, detail: item.dangerous ? "冒险" : item.cost === 0 ? "不耗时" : "30分钟",
      select: () => onExecute(item) })),
    { id: "map", label: "沿走廊，去其他地方", available: true, detail: "查看楼层图", select: onMap },
    { id: "people", label: "找人当面交谈", available: state.npcs.some(person => person.availableTalk),
      detail: "选择要见的人", select: () => setPeople(true) },
  ];

  return <>
    {complete && !reading && !state.result && !composer && !busy && !state.sceneCue && !state.pendingSpeakers.length
      && <div className="vn-decisions" aria-label="接下来怎么做">
      <span className="vn-decision-caption">{event?.kind === "danger" ? "你必须在这里作出选择" : "接下来，你决定…"}</span>
      <div className="vn-choice-list">
        {people ? <>
          {state.npcs.filter(person => person.availableTalk).map(person => <button key={person.id} disabled={locked}
            onClick={() => action("approach", { npcId: person.id, version: state.version })}>
            <span>{person.name}</span><small>{person.role}</small>
          </button>)}
          <button className="vn-back-choice" onClick={() => setPeople(false)}>返回行动选项</button>
        </> : choices.map((item, index) => <button key={item.id} disabled={locked || !item.available}
          className={item.dangerous ? "danger-choice" : ""}
          onClick={item.select}>
          <i aria-hidden="true">{String(index + 1).padStart(2, "0")}</i>
          <span>{item.label}</span>
          <small>{item.available ? item.detail : item.reasons?.join("；")}</small>
        </button>)}
      </div>
    </div>}

    <section className={`vn-dialogue${event?.kind === "danger" ? " is-danger" : ""}`} aria-label="故事对白">
      <div className="vn-nameplate">
        <span>{current?.name || "旁白"}</span>
        <small>{current?.note || (event?.kind === "danger" ? "险情仍在发生" : event?.title || "永昼病院 · 第七夜")}</small>
      </div>
      <button className="vn-line" onClick={next} disabled={!typing && position >= frames.length - 1}
        aria-label={`${typing ? "显示完整文字" : "继续阅读"}：${current?.name || "旁白"}，${current?.text || ""}`}>
        <span className="vn-line-text">{current?.text.slice(0, visible) || " "}</span>
        {!typing && position < frames.length - 1 && <span className="vn-continue-mark" aria-hidden="true">▼</span>}
      </button>
      <footer className="vn-dialogue-footer">
        <div className="vn-reading-state">
          <span>{String(Math.min(position + 1, frames.length)).padStart(2, "0")} / {String(frames.length).padStart(2, "0")}</span>
          {busy ? <span className="vn-generating" role="status"><i className="spinner" />{busy}</span>
            : typing ? <span>点击对白显示全文</span> : !complete ? <span>点击对白继续</span>
              : <span>{event && !event.paid ? "本现场结束时推进30分钟" : "阅读对白不耗时"}</span>}
        </div>
        <div className="vn-tools">
          <button onClick={onLog}>回看</button>
          {npc && !reading && !state.result && <button onClick={event => openComposer("speech", event.currentTarget)}
            aria-expanded={composer === "speech"}>对{npc.name}说话</button>}
          {!reading && !state.result && <details ref={moreMenu} className="vn-more"
            onBlur={event => {
              if (!event.currentTarget.contains(event.relatedTarget)) event.currentTarget.open = false;
            }} onKeyDown={event => {
              if (event.key === "Escape") {
                event.currentTarget.open = false;
                event.currentTarget.querySelector("summary")?.focus();
              }
            }}>
            <summary>更多</summary>
            <div className="vn-more-menu">
              <button onClick={() => openComposer("action")}>自由描述行动</button>
            </div>
          </details>}
          {typing || !complete ? <button className="vn-next" onClick={next}>{typing ? "显示全文" : "继续"} <span>›</span></button>
            : reading ? <button className="vn-next" disabled={locked} onClick={() => action("advance")}>开始夜班 <span>›</span></button>
              : <button className="vn-next" onClick={onBook}>查看须知</button>}
        </div>
      </footer>
      {game.busyHint && <p className="vn-wait-hint" role="status">{game.busyHint}</p>}
      {!busy && (state.sceneCue || state.pendingSpeakers.length > 0) && <div className="vn-retry">
        <span>{state.sceneCue?.kind === "speech" ? "原话的回应尚未完成。" : "人物的回应尚未完成，现场结果已保存。"}</span>
        <button onClick={game.resumeTurns}>接续回应</button>
        {state.sceneCue && <button onClick={() => action("silence", { cueId: state.sceneCue.id })}>先做眼前的事</button>}
      </div>}
    </section>

    <div className="vn-composer-backdrop" hidden={!composer} onClick={() => setComposer(false)}>
      <section ref={drawer} className="vn-composer" role="dialog" aria-modal="true"
        aria-label={composer === "speech" && npc ? `对${npc.name}说话` : "自由描述行动"} tabIndex={-1}
        onClick={event => event.stopPropagation()} onKeyDown={event => {
          if (event.key === "Escape") setComposer(false);
          if (event.key === "Tab") {
            const controls = [...drawer.current.querySelectorAll("button:not(:disabled),textarea:not(:disabled),input:not(:disabled),summary")];
            const first = controls[0], last = controls.at(-1);
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
          }
        }}>
        <header><div><span className="eyebrow">以许舟的身份</span>
          <h2>{composer === "speech" && npc ? `对${npc.name}说话` : "自由描述行动"}</h2></div>
          <button onClick={() => setComposer(false)}>回到故事 ×</button></header>
        <DungeonConversation game={game} narration={narration} npc={npc} mode={composer || "action"}
          onSubmitted={() => setComposer(false)} />
      </section>
    </div>
  </>;
}
