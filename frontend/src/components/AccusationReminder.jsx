export function AccusationReminder({ readiness, nextLabel, locked, onContinue, onConfirm }) {
  return <div className="dialog-backdrop" onClick={onContinue}>
    <section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="accusation-title"
      aria-describedby="accusation-description" onClick={(event) => event.stopPropagation()}
      onKeyDown={(event) => {
        if (event.key === "Escape") onContinue();
        if (event.key === "Tab") {
          const buttons = [...event.currentTarget.querySelectorAll("button:not(:disabled)")];
          const first = buttons[0], last = buttons.at(-1);
          if (first && event.shiftKey && document.activeElement === first) {
            event.preventDefault(); last.focus();
          } else if (last && !event.shiftKey && document.activeElement === last) {
            event.preventDefault(); first.focus();
          }
        }
      }}>
      <span className="eyebrow">结束调查之前</span><h2 id="accusation-title">准备进入{nextLabel}？</h2>
      <p id="accusation-description">进入后将结束私聊、搜证和公聊，不能返回调查阶段。你仍可选择保留秘密，不必公开全部线索。</p>
      {readiness && <>
        <p>已搜 {readiness.searchedCount} 个地点 · 当前公开 {readiness.publicEvidenceCount} 条线索
          （新增 {readiness.newPublicEvidenceCount} 条）。</p>
        {readiness.warnings.length > 0
          ? <ul className="facts">{readiness.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
          : <p>当前没有剩余搜索机会，已有新线索公开。线索数量不代表真相已经查明，请确认是否还需要交流核实。</p>}
      </>}
      <div><button autoFocus onClick={onContinue}>继续调查</button>
        <button className="primary" disabled={locked} onClick={onConfirm}>确认进入{nextLabel}</button></div>
    </section>
  </div>;
}
