export function EvidenceCard({ item, isPublic, onPublish, disabled }) {
  return <article className="evidence-card">
    <span className="eyebrow">{isPublic ? "全桌可见" : "你持有的线索"}{item.kind === "testimony" ? " · 记忆与证词" : ""}</span>
    <h3>{item.title}</h3><p>{item.summary}</p>
    <details><summary>查看细节</summary><p>{item.detail}</p></details>
    {onPublish && !isPublic && <button className="small-button" disabled={disabled}
      onClick={() => onPublish(item.id)}>公开给全桌</button>}
  </article>;
}

export function EvidenceGrid({ items, state, locked, action, share = false }) {
  const publicIds = new Set(state.publicEvidence.map((item) => item.id));
  return <div className="evidence-grid">{items.map((item) => <EvidenceCard key={item.id} item={item}
    isPublic={publicIds.has(item.id)} disabled={locked || !state.allowedActions.includes("publish")}
    onPublish={share ? (evidenceId) => action("publish", { evidenceId }) : undefined} />)}</div>;
}
