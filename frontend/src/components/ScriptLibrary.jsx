export function ScriptLibrary({ scripts, busy, onSelect }) {
  return <main className="library">
    <section className="library-intro">
      <div><span className="eyebrow">独自赴约 · 与 AI 同桌</span>
        <h1>挑一个故事，<br /><em>成为局中人。</em></h1>
        <p>每个人都有自己的过去，也有不愿说出口的秘密。<br />领取你的身份，和他们一起，把这一夜走到最后。</p>
      </div>
      <div className="library-note"><span>入局须知 / 01</span><p>你也有一份私人剧本。<br />可以坦白，也可以隐瞒。<br />真相只有一个，立场各不相同。</p><small>角色对话由 AI 实时生成</small></div>
    </section>
    <div className="library-heading"><h2>故事陈列室</h2><span>{scripts.length} 个剧本 · 一人入局</span></div>
    <div className="script-grid">{scripts.map((script, index) => <button
      className={`script-card theme-${script.theme}`} key={script.id} disabled={Boolean(busy)}
      onClick={() => onSelect(script.id)}>
      <div className="script-cover" aria-hidden="true">
        <span className="cover-index">CASE / {String(index + 1).padStart(2, "0")}</span>
        <div className={`cover-symbol symbol-${script.theme}`}><span>{script.coverText}</span></div>
        <span className="cover-caption">{script.locationLabel} · {script.gameType === "dungeon" ? "生存副本" : `${script.playerCount} 人本`}</span>
      </div>
      <div className="script-body">
        <div className="script-meta"><span>{script.availability.status === "ready" ? script.difficulty : "待补齐原作"}</span><span>{script.duration}</span></div>
        <h3>{script.title}</h3><p className="script-subtitle">{script.subtitle}</p>
        <p className="script-description">{script.summary}</p>
        <div className="script-tags">{script.tags.map((tag) => <span key={tag}>{tag}</span>)}</div>
        <div className="script-bottom">
          <span>{script.progress.started ? `${script.progress.playerName} · ${script.progress.phaseLabel}`
            : script.availability.status === "ready" ? `${script.playerCount - 1} 位 AI 陪玩 · ${script.mode.label}` : "官方资料已收录 · 暂不能开局"}</span>
          <strong>{script.progress.started ? "继续这一局" : script.availability.status === "ready" ? "选择剧本" : "查看资料"} ↗</strong>
        </div>
      </div>
    </button>)}</div>
    <p className="library-footnote">各剧本独立保留本次服务运行期间的进度。离开一个故事，不会结束另一张桌。</p>
  </main>;
}
