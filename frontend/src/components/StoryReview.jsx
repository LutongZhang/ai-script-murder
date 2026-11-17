import { useState } from "react";

export function StoryReview({ characters, evidence = [] }) {
  const [expanded, setExpanded] = useState(() => new Set());
  if (!characters?.length) return null;
  const allExpanded = characters.every((person) => expanded.has(person.id));
  return <section className="story-review" aria-labelledby="story-review-title">
    <div className="section-title">
      <h3 id="story-review-title">全人物剧情复盘 · {characters.length} 人</h3>
      <button className="small-button" onClick={() => setExpanded(
        allExpanded ? new Set() : new Set(characters.map((person) => person.id)))}>
        {allExpanded ? "收起全部人物" : "展开全部人物"}
      </button>
    </div>
    <p className="muted">面具卸下之后，回看每个人真正经历的故事。人物经历和秘密来自剧本设定；关系描述保留该角色当时的视角。</p>
    <div className="story-characters">{characters.map((person) => <article className="story-character" key={person.id}>
      <h4><button className="story-toggle" aria-expanded={expanded.has(person.id)} aria-controls={`story-${person.id}`}
        onClick={() => setExpanded((old) => {
          const next = new Set(old);
          if (next.has(person.id)) next.delete(person.id); else next.add(person.id);
          return next;
        })}>
        <span>{person.name}<small>{person.role}</small></span>
        <span className="story-badges">
          {person.isPlayer && <span>你扮演的角色</span>}
          <span className={person.isKiller ? "killer-badge" : ""}>{person.isKiller ? "本案凶手" : "非凶手"}</span>
          <span aria-hidden="true">{expanded.has(person.id) ? "−" : "＋"}</span>
        </span>
      </button></h4>
      <div id={`story-${person.id}`} className="story-content" hidden={!expanded.has(person.id)}>
        <h5>人物背景</h5><p className="muted">{person.publicProfile}</p><p>{person.intro}</p>
        <div className="secret"><h5>真正藏着的事</h5><p>{person.secret}</p></div>
        <h5>个人经历与已知事实</h5><ul className="facts">{person.facts.map((fact, index) => <li key={index}>{fact}</li>)}</ul>
        <h5>人物关系 · 该角色的视角</h5><div className="story-relations">{person.relationships.map((relation) => <p key={relation.roleId}>
          <strong>{relation.name}</strong>{relation.description}</p>)}</div>
        <h5>原本想达成的目标</h5><ul className="goals">{person.goals.map((goal, index) => <li key={index}>◇ {goal}</li>)}</ul>
        {person.approach && <><h5>原本的应对与取舍</h5><p>{person.approach}</p></>}
        {person.evidenceIds.length > 0 && <>
          <h5>角色本关联线索</h5><p className="muted">包括初始线索与搜证安排；不代表本局全部取得或公开。</p>
          <div className="story-clues">{evidence.filter((clue) => person.evidenceIds.includes(clue.id)).map((clue) => <details key={clue.id}>
            <summary>{clue.title} · {clue.kind === "testimony" ? "记忆证词" : "物证"}</summary>
            <p>{clue.detail}</p>
          </details>)}</div>
        </>}
      </div>
    </article>)}</div>
    {evidence.length > 0 && <details className="review-evidence">
      <summary>全部线索解读 · {evidence.length} 条 · 包含本局未发现的线索</summary>
      <div className="story-clues">{evidence.map((clue) => <article key={clue.id}>
        <h5>{clue.title}<small>{clue.kind === "testimony" ? "记忆证词" : "物证"}</small></h5>
        <p className="muted">{clue.summary}</p><p>{clue.detail}</p>
      </article>)}</div>
    </details>}
  </section>;
}
