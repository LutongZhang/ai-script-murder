import { useEffect, useRef, useState } from "react";

export function DungeonConversation({ game, narration, npc }) {
  const { state, busy, action, privateErrors } = game;
  const [drafts, setDrafts] = useState({});
  const [presenting, setPresenting] = useState([]);
  const [mode, setMode] = useState("action");
  const input = useRef(null);
  const key = npc?.id || "scene";
  const turns = state.privateChats[npc?.id] || [];
  const event = state.encounter;
  const sceneTurns = event ? turns.filter(turn => turn.encounterId === event.id) : turns;
  const latest = sceneTurns.at(-1);
  const error = privateErrors[`${state.case.id}:${npc?.id}`];
  const locked = Boolean(busy) || state.pendingSpeakers.length > 0 || !state.allowedActions.includes("private");
  useEffect(() => { setPresenting([]); setMode("action"); }, [npc?.id, event?.id]);

  return <div className="scene-conversation">
    <div className="scene-input-modes" aria-label="行动或说话">
      <button type="button" aria-pressed={mode === "action"} onClick={() => setMode("action")}>描述我的行动</button>
      {npc && <button type="button" aria-pressed={mode === "speech"} onClick={() => setMode("speech")}>对{npc.name}说话</button>}
    </div>
    {mode === "speech" && <span className="eyebrow">只有{npc.name}听见 · 可以连续追问</span>}
    {!event && latest && mode === "speech" && <div className="scene-private-reply" aria-live="polite">
      <small>你：{latest.question}</small>
      <p>{narration.replyText(`${state.case.id}:private-${npc.id}-${turns.length - 1}`, latest.response)}</p>
      {latest.actionLabel && <span className="scene-npc-action">对方的行动：{latest.actionLabel}</span>}
      {latest.evidenceIds?.length > 0 && <span className="scene-gift">交给你的材料：{latest.evidenceIds.map(id => state.hand.find(item => item.id === id)?.title || id).join("、")}</span>}
    </div>}
    <form onSubmit={event => {
      event.preventDefault();
      if (!locked && drafts[key]?.trim()) action(mode === "speech" ? "question" : "scene-action",
        mode === "speech" ? { npcId: npc.id, question: drafts[key], evidenceIds: presenting, version: state.version }
          : { message: drafts[key], version: state.version },
        () => { setDrafts(old => ({ ...old, [key]: "" })); setPresenting([]); });
    }}>
      {mode === "speech" && error && <p className="scene-chat-error" role="alert">{error} 输入已保留，本次交谈未扣时。</p>}
      <textarea ref={input} aria-label={mode === "speech" ? `给${npc.name}的私聊` : "描述你在现场的行动"} rows={3} maxLength={2000}
        placeholder={mode === "speech" ? "以许舟的身份开口……" : "我蹲下去听门后的动静……\n写你要做什么；想说的话也可以直接写在这里。"} disabled={Boolean(busy)}
        value={drafts[key] || ""} onChange={event => setDrafts(old => ({ ...old, [key]: event.target.value }))} />
      {mode === "speech" && <details className="scene-present"><summary>私下出示材料{presenting.length ? ` · 已选${presenting.length}件` : ""}</summary>
        {state.hand.map(item => <label key={item.id}><input type="checkbox" disabled={locked} checked={presenting.includes(item.id)}
          onChange={event => setPresenting(old => event.target.checked ? [...old, item.id] : old.filter(id => id !== item.id))} />{item.title}</label>)}
        <small>随这句话交给对方看，其他人不会收到。</small>
      </details>}
      <div><span>{event ? "眼前的事还没结束。你可以继续做，也可以开口。" : "人物会看见你的做法，也会记住你说的话。"}</span><button className="primary" disabled={locked || !drafts[key]?.trim()}>
        {busy ? "等待现场回应…" : mode === "speech" ? "开口" : "就这样做"}</button></div>
    </form>
    {npc && turns.length > 1 && <details className="scene-conversation-history"><summary>与{npc.name}之前的谈话</summary>
      {turns.slice(0, -1).map((turn, index) => <article key={`${npc.id}-${index}`}>
        <small>{turn.question ? `你：${turn.question}` : `${npc.name}先开口`}</small><p>{turn.response}</p>
      </article>)}
    </details>}
  </div>;
}
