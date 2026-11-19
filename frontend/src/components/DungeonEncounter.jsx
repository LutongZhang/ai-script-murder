import { DungeonConversation } from "./DungeonConversation.jsx";
import { useEffect, useRef } from "react";

export function DungeonEncounter({ game, narration }) {
  const { state, busy, action } = game;
  const event = state.encounter;
  const npc = state.npcs.find(person => person.id === event.npcId);
  const transcript = useRef(null);
  useEffect(() => {
    if (transcript.current) transcript.current.scrollTop = transcript.current.scrollHeight;
  }, [event.log.length]);
  return <div className={`scene-encounter${event.kind === "danger" ? " is-danger" : ""}`} aria-label="当前互动现场">
    <div className="scene-encounter-title"><span className="eyebrow">{event.kind === "danger" ? "险情仍在发生" : "你正在现场"}</span>
      <small>{event.paid ? "上一行动已扣时，应对选择另有说明" : "结束本现场通常过去30分钟"}</small></div>
    <h2>{event.title}</h2>
    <p className="scene-description">{event.description}</p>
    {state.world.anomaly > 0 && <p className="scene-body">{state.body}</p>}
    {event.log.length > 0 && <div ref={transcript} className="scene-transcript" aria-live="polite">
      {event.log.map((entry, i) => <article key={i} className={entry.speakerId ? "is-speech" : "is-physical"}>
        {entry.speakerId && <small>{entry.speakerName}</small>}
        <p>{entry.text}</p>
        {entry.actionLabel && <span className="scene-npc-action">{entry.actionLabel}</span>}
      </article>)}
    </div>}
    <DungeonConversation key={`${event.id}:${npc?.id || "scene"}`} game={game} narration={narration} npc={npc} />
    {state.sceneCue && !busy && <div className="scene-reaction-retry"><span>{state.sceneCue.kind === "speech"
      ? "这句话尚未得到回复，可以接续原话，也可以先不谈。"
      : "对方的声音还未传来。你可以继续处理眼前的事。"}</span>
      <button onClick={game.resumeTurns}>接续人物回复 · 不重复扣时</button>
      <button onClick={() => action("silence", { cueId: state.sceneCue.id })}>先做眼前的事</button>
    </div>}
    <details className="scene-affordances"><summary>{event.kind === "danger" ? "眼前可以怎样应对" : "看看眼前能动的物件"}</summary>
    <div className="scene-encounter-choices" aria-label="现场选择">
      {event.choices.map(item => <button key={item.id} disabled={Boolean(busy) || !item.available}
        className={item.dangerous ? "danger-choice" : ""}
        onClick={() => action("choice", { encounterId: event.id, choiceId: item.id, version: state.version })}>
        <span>{item.label}</span><small>{item.available ? item.detail : item.reasons.join("；")}</small>
      </button>)}
    </div>
    </details>
    {busy && <div className="scene-wait" role="status"><span className="spinner" />{busy}
      {game.busyHint && <p className="scene-wait-explanation">{game.busyHint}</p>}</div>}
  </div>;
}
