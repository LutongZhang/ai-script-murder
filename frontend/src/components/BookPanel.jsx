import { EvidenceGrid } from "./EvidenceCard.jsx";

export function BookPanel({ state, locked, action }) {
  const player = state.player;
  return <div className="book-panel">
    {state.playMode === "killer" && <div className="secret"><h3>凶手模式 · 你已知自己的罪行</h3>
      <p>先读清自己的作案经历、秘密与个人目标，再决定如何回应其他人。你仍需搜证和交流，才能知道别人掌握了什么；最终能否隐藏身份，由大家的指认决定。</p></div>}
    <section className="book-opening" aria-labelledby="opening-title">
      <span className="eyebrow">共同背景 · 所有人已知</span><h2 id="opening-title">开局之前，发生了什么</h2>
      <p>{state.case.opening || state.case.summary}</p>
      {state.case.timeline.length > 0 && <>
        <h3>公开的时间顺序</h3>
        <ol className="facts">{state.case.timeline.map((event) => <li key={`${event.time}:${event.title}`}>
          <strong>{event.time} · {event.title}</strong><p>{event.detail}</p>
        </li>)}</ol>
      </>}
    </section>
    <span className="eyebrow">私人剧本 · 只有你可见</span><h2>{player.name}的故事</h2>
    <p className="intro-text">{player.intro}</p>
    <div className="secret"><h3>你藏着的事</h3><p>{player.secret}</p></div>
    <h3>你记得的经过</h3><ul className="facts">{player.facts.map((fact) => <li key={fact}>{fact}</li>)}</ul>
    <h3>你想达成的目标</h3><ul className="goals">{player.goals.map((goal) => <li key={goal}>◇ {goal}</li>)}</ul>
    {player.approach && <><h3>被怀疑时如何应对</h3><p>{player.approach}</p></>}
    <h3>你与他们的关系</h3><div className="relations">{state.npcs.map((person) => <p key={person.id}>
      <strong>{person.name}</strong>{player.relationships[person.id]}</p>)}</div>
    <div className="section-title"><h3>你的线索 · {state.hand.length}</h3><span>私聊收到和搜到的线索 · 公聊时可选择公开</span></div>
    <EvidenceGrid items={state.hand} state={state} locked={locked} action={action} share />
  </div>;
}
