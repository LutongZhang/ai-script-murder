export function RoleLobby({ state, busy, onStart, onStartKiller, onBack }) {
  const script = state.case;
  const playable = script.availability.status === "ready";
  return <main className="lobby">
    <button className="back-link" disabled={Boolean(busy)} onClick={onBack}>← 返回剧本库</button>
    <div className="lobby-intro">
      <span className="eyebrow">{script.playerCount} 人本 / {script.tags.join(" · ")} / {script.duration}</span>
      <h1>{script.title}<span className="lobby-title-note">{playable ? "选择你的身份" : "原作资料待补齐"}</span></h1>
      <p>{script.summary}</p>{playable && <p className="muted">领取一份私人剧本。其余 {script.playerCount - 1} 人由 AI 扮演，会隐瞒、交换线索、互相质疑，也会独立投票。</p>}
      {script.availability.note && <p className={playable ? "muted" : "material-note"}>{script.availability.note}</p>}
      {script.source && <details className="script-source"><summary>原作来源与适配说明</summary>
        <p>{script.source.title} · {script.source.publisher}<br />{script.source.language}<br />{script.source.completeness}</p>
        <p>{script.source.note}</p>
        <a href={script.source.url} target="_blank" rel="noreferrer">打开官方{playable ? "来源" : "免费领取入口"} ↗</a>
      </details>}
    </div>
    <section className="killer-entry" aria-labelledby="killer-mode-title">
      <div><span className="eyebrow">直接进入另一种立场</span><h2 id="killer-mode-title">凶手模式</h2>
        <p>{playable ? "直接领取本案凶手的私人剧本，掌握自己的作案经历。保护秘密、应对质疑，争取不被指认；其余角色由 AI 扮演。"
          : "完整凶手角色本与案情尚未取得，材料补齐后才能直接扮演凶手。"}</p></div>
      <button className="primary" disabled={Boolean(busy) || !playable} onClick={onStartKiller}>
        {playable ? "直接扮演凶手 →" : "凶手角色本待补齐"}</button>
    </section>
    <h2>自由选择角色</h2>
    <div className="role-grid">{state.roles.map((role, index) => <button key={role.id}
      className={`role-card seat-${index % 4}`} disabled={Boolean(busy) || !playable} onClick={() => onStart(role.id)}>
      <span className="seat-number">席位 {String(index + 1).padStart(2, "0")}</span>
      <div className="portrait" aria-hidden="true"><span>{role.name[0]}</span></div>
      <span className="role-name">{role.name}</span><span className="role-title">{role.role}</span>
      <p>{role.publicProfile}</p><span className="take-role">{playable ? "领取剧本 ↗" : "私人角色本待补齐"}</span>
    </button>)}</div>
    <div className="lobby-footer">{playable ? state.phases.join(" → ") : "获取完整材料后才能入局"}<span>{script.mode.label}</span></div>
  </main>;
}
