import { EvidenceGrid } from "./EvidenceCard.jsx";

export function SearchPanel({ state, locked, action }) {
  const followup = state.phaseKind === "discussion" && state.allowedActions.includes("search");
  return <div>
    <span className="eyebrow">{state.case.locationLabel}{followup ? "补查" : "搜证"}</span>
    <h2>{followup ? "补查尚未搜索的地点" : "去哪里看看？"}</h2>
    <p className="muted">{state.allowedActions.includes("search") ? `本阶段还能搜 ${state.searchesLeft} 个地点。发现的线索先只放入你的手牌。`
      : `本局共可搜索 ${state.case.searchLimit} 个地点，开放阶段以剧本流程为准；发现保留在私人剧本中。`}</p>
    <div className="location-grid">{state.locations.map((location, index) => <button className="location" key={location.id}
      disabled={locked || !location.available || location.searched || !state.searchesLeft}
      onClick={() => action("search", { locationId: location.id })}>
      <span className="eyebrow">地点 / {String(index + 1).padStart(2, "0")}</span>
      <h3>{location.name}</h3><p>{location.description}</p>
      <span className="take-role">{location.searched ? "已搜过 ✓" : !location.available ? "本阶段未开放"
        : !state.searchesLeft ? "本阶段次数已用完" : state.pendingSpeakers.length ? "本轮公聊结束后可搜索" : "搜索这里 ↗"}</span>
    </button>)}</div>
    <div className="section-title"><h3>你的线索 · {state.hand.length}</h3><span>公聊时由你决定是否公开</span></div>
    <EvidenceGrid items={state.hand} state={state} locked={locked} action={action} share />
  </div>;
}
