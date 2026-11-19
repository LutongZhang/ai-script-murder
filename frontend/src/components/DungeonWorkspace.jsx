import { useCallback, useEffect, useRef, useState } from "react";
import { BookPanel } from "./BookPanel.jsx";
import { EvidenceGrid } from "./EvidenceCard.jsx";
import { DungeonNovel } from "./DungeonNovel.jsx";
import { DeathSequence } from "./DeathSequence.jsx";
import { useDeathSound } from "../hooks/useDeathSound.js";
import { CHARACTERS, SCENES, sceneActions } from "../hooks/dungeonScene.js";
import "../dungeon.css";

export function DungeonWorkspace({ game, narration }) {
  const { state, busy, action } = game;
  const { world } = state;
  const [panel, setPanel] = useState(state.phaseKind === "reading" ? "book" : null);
  const [destination, setDestination] = useState(null);
  const [risk, setRisk] = useState(null);
  const [found, setFound] = useState([]);
  const [portraitFailed, setPortraitFailed] = useState(false);
  const [backgroundStatus, setBackgroundStatus] = useState("loading");
  const [imageAttempt, setImageAttempt] = useState(0);
  const [speakerId, setSpeakerId] = useState(null);
  const [deathActive, setDeathActive] = useState(null);
  const previousResult = useRef(state.result?.id);
  const [soundEnabled, setSoundEnabled] = useState(() => {
    try { return localStorage.getItem("script-kill.horror-sound") !== "off"; } catch { return true; }
  });
  const deathSound = useDeathSound(soundEnabled, {
    location: world.location, night: world.night,
    danger: state.encounter?.kind === "danger", ended: Boolean(state.result),
  });
  const deathCause = world.anomaly >= world.anomalyLimit ? "caught" : "sealed";
  const finishDeath = useCallback(() => {
    setDeathActive(null);
    requestAnimationFrame(() => {
      const ending = document.getElementById("dungeon-ending");
      ending?.focus({ preventScroll: true });
      ending?.scrollIntoView({ block: "start", behavior: "instant" });
    });
  }, []);
  function toggleSound() {
    setSoundEnabled(old => {
      try { localStorage.setItem("script-kill.horror-sound", old ? "off" : "on"); } catch { /* Optional storage. */ }
      return !old;
    });
  }
  const sceneRef = useRef(null);
  const reading = state.phaseKind === "reading";
  const locked = Boolean(busy) || state.pendingSpeakers.length > 0 || reading || Boolean(state.encounter);
  const location = state.locations.find(item => item.id === world.location);
  const scene = SCENES[world.location];
  const clues = [...state.hand, ...state.publicEvidence];
  const knownClues = useRef(new Set(clues.map(item => item.id)));
  const pendingNpc = state.pendingSpeakers[0];
  const npc = state.npcs.find(person => person.id === (state.presentNpcId || pendingNpc));
  const knownRoom = clues.find(item => item.id === "roster")?.summary.match(/(307|309)/)?.[1];
  const sisterHere = world.flags.sisterRescued || (world.flags.sisterVerified && world.location === `ward${knownRoom}`);
  const characterId = state.encounter?.source === "patrol" ? "patrol" : speakerId || npc?.id || (sisterHere ? "sister" : null);
  const character = CHARACTERS[characterId];
  const characterPerson = state.npcs.find(person => person.id === characterId);
  const visibleActions = sceneActions(state, world.location);
  const evidenceHere = clues.filter(item => scene.evidence.includes(item.id));
  const conversationOpen = Boolean(state.encounter) && !state.result;

  useEffect(() => {
    const ids = [...state.hand, ...state.publicEvidence].map(item => item.id);
    const newIds = ids.filter(id => !knownClues.current.has(id));
    if (newIds.length) setFound(newIds);
    knownClues.current = new Set(ids);
  }, [state.hand, state.publicEvidence]);

  useEffect(() => {
    // Preload fixed artwork; these images contain no randomized clue values.
    const images = Object.values({ ...SCENES, ...CHARACTERS }).map(item => {
      const img = new Image();
      img.src = item.image;
      return img;
    });
    return () => { images.forEach(img => { img.onload = null; img.onerror = null; }); };
  }, []);

  useEffect(() => { setPortraitFailed(false); }, [characterId, imageAttempt]);
  useEffect(() => { setBackgroundStatus("loading"); }, [world.location]);
  useEffect(() => {
    if (state.result) {
      setPanel(null);
      if (state.result.id === "failure" && previousResult.current !== "failure") {
        narration.stopSpeech();
        setDeathActive(deathCause);
      } else window.scrollTo({ top: 0, behavior: "instant" });
    }
    previousResult.current = state.result?.id;
  }, [state.result?.id]);

  function execute(item) {
    setPanel(null); setDestination(null); setFound([]);
    sceneRef.current?.scrollIntoView({ block: "start", behavior: "smooth" });
    if (item.dangerous) setRisk({ ...item, version: state.version });
    else action("act", { actionId: item.id, version: state.version });
  }

  function search(locationId) {
    setPanel(null); setDestination(null); setFound([]);
    sceneRef.current?.scrollIntoView({ block: "start", behavior: "smooth" });
    action("search", { locationId, version: state.version }, data => {
      const ids = [...data.hand, ...data.publicEvidence].map(item => item.id);
      setFound(ids.filter(id => !knownClues.current.has(id)));
    });
  }

  const foundItems = clues.filter((item, index) => found.includes(item.id) && clues.findIndex(other => other.id === item.id) === index);

  return <main className={`dungeon-workspace scene-workspace vn-workspace${world.night ? " is-night" : ""}`}>
    <div className="scene-quest">
      <div><span className="eyebrow">第七夜 / 你是许舟</span><p>{state.result ? state.result.title : world.flags.sisterRescued ? "许宁已跟随你。带她走出病院。" : "找到妹妹许宁，带她回家。"}</p></div>
      <nav aria-label="随身物品与记录">
        <button onClick={() => setPanel("map")}>楼层图</button>
        <button onClick={() => setPanel("clues")}>线索 <span>{state.hand.length}</span></button>
        <button onClick={() => setPanel("book")}>值班须知</button>
        <button onClick={() => setPanel("log")}>夜班记录</button>
        <button aria-pressed={soundEnabled} onClick={toggleSound}>音效{soundEnabled ? "开" : "关"}</button>
      </nav>
    </div>

    <section ref={sceneRef} className={`night-scene vn-stage${world.anomaly ? " has-anomaly" : ""}${state.encounter?.kind === "danger" ? " is-danger" : ""}`} aria-label={`${location.name}场景`}>
      <img key={`${world.location}:${imageAttempt}`} className={`scene-background${backgroundStatus === "ready" ? " ready" : ""}`}
        src={scene.image} alt={`永昼病院 · ${location.name}的夜间场景`} fetchPriority="high"
        onLoad={event => setBackgroundStatus(isServiceDefault(event.currentTarget) ? "pending" : "ready")}
        onError={() => setBackgroundStatus("failed")} />
      <div className="scene-vignette" aria-hidden="true" />
      {backgroundStatus !== "ready" && <div className="scene-image-status" role="status">
        <p>{backgroundStatus === "failed" ? "场景图片暂未加载。" : backgroundStatus === "pending" ? "场景图片尚未就绪。" : "场景正在显现…"}</p>
        {backgroundStatus !== "loading" && <button onClick={() => { setBackgroundStatus("loading"); setImageAttempt(Date.now()); }}>重新加载图片</button>}
      </div>}
      <header className="scene-hud">
        <div><span className="eyebrow">永昼病院 · 三楼</span><h1>{location.name}</h1></div>
        <div className="scene-clock" aria-label={`病院时钟 ${world.time}`}><strong>{world.time}</strong>
          <span>{world.exitOpen ? "出口窗口开启" : world.night ? "熄灯后的夜班" : "离天亮还有很久"}</span></div>
      </header>
      <div className="scene-risk" aria-label={`异常 ${world.anomaly}，上限 ${world.anomalyLimit}`}>
        <span>异常</span>{Array.from({ length: world.anomalyLimit }, (_, i) => <i key={i} className={i < world.anomaly ? "filled" : ""} />)}
        <small>{world.turn}/{world.maxTurns} 次行动</small>
      </div>
      {sisterHere && <div className="scene-companion">
        <i aria-hidden="true">◇</i><span>许宁<small>{world.flags.sisterRescued ? "跟在你身旁" : "身份已经核验"}</small></span>
      </div>}

      {character && !portraitFailed && !reading && <figure className={`scene-character${characterId === "caller" ? " is-intercom" : ""}`} key={characterId}>
        <img key={imageAttempt} src={character.image} alt={characterId === "patrol" ? "无脸巡查员正在门外" : characterId === "sister" ? "许宁的人物形象" : characterId === "caller" ? "广播扬声器，来电者没有已核验的人物形象" : `${characterPerson?.name || "在场人物"}的人物形象`}
          onLoad={event => { if (isServiceDefault(event.currentTarget)) setPortraitFailed(true); }}
          onError={() => setPortraitFailed(true)} />
        <figcaption>{characterId === "patrol" ? "门外的巡查员" : characterId === "sister" ? world.flags.sisterVerified ? "许宁 · 已核验身份" : "床边的女孩 · 尚待问答核验" : `${characterPerson?.name || "传来的声音"} · ${conversationOpen ? "私下交谈" : "传来的回应"}`}</figcaption>
      </figure>}

      {foundItems.length > 0 && <div className="vn-found" role="status">
        <span>◇ 发现线索</span><strong>{foundItems.map(item => item.title).join("、")}</strong>
        <button onClick={() => setPanel("found")}>查看</button><button aria-label="收好新线索" onClick={() => setFound([])}>×</button>
      </div>}
      <DungeonNovel game={game} narration={narration} npc={npc} location={location} scene={scene}
        actions={visibleActions} onExecute={execute} onSearch={search} onMap={() => setPanel("map")}
        onBook={() => setPanel("book")} onLog={() => setPanel("log")} onSpeaker={setSpeakerId} />
    </section>

    {state.result && !deathActive && <DungeonEnding state={state} action={action} narration={narration}
      replay={() => { narration.stopSpeech(); setDeathActive(deathCause); }} />}

    <p className="dungeon-source">{state.case.source.attribution} <a href={state.case.source.url} target="_blank" rel="noreferrer">原作</a> · <a href={state.case.source.licenseUrl} target="_blank" rel="noreferrer">{state.case.source.license}</a></p>

    {panel && <SceneDialog title={panel === "map" ? "永昼病院 · 三楼" : panel === "clues" ? "随身线索" : panel === "log" ? "这一夜的记录" : panel === "found" ? "刚取得的线索" : panel === "local" ? `${location.name} · 手边的材料` : "许舟 · 值班前的笔记"} onClose={() => { setPanel(null); setDestination(null); }}>
      {panel === "book" && <><BookPanel state={state} locked={Boolean(busy)} action={action} />
        <h3>六条值班须知</h3><ol className="facts">{state.rules.map(rule => <li key={rule.id}>{rule.text}</li>)}</ol>
        <p className="muted">一次调查、行动或交涉结束，通常过去半小时。同一现场可以连续翻查、追问和私下出示材料；选择独自慢慢处理会多花时间。05:00出口开启，07:00关闭。核验需要妹妹亲口回答，带离病床仍需单独行动。</p>
        {reading && <button className="primary" disabled={Boolean(busy)} onClick={() => action("advance", {}, () => setPanel(null))}>收起须知，开始夜班 →</button>}</>}
      {panel === "map" && <><p className="muted">你现在在{location.name}。选地点查看能做的事；前往调查或执行行动时，才会移动并耗时。</p>
        <div className="night-map">{state.locations.map(loc => <button key={loc.id} aria-pressed={(destination || world.location) === loc.id}
          onClick={() => setDestination(loc.id)}><span>{loc.name}</span><small>{loc.id === world.location ? "你在这里" : loc.searched ? "已调查" : "尚未调查"}</small></button>)}</div>
        <Destination state={state} locationId={destination || world.location} locked={locked} execute={execute} search={search} /></>}
      {panel === "clues" && <><p className="muted">公开的材料会被所有人物看见，包括广播里的声音。</p>
        <EvidenceGrid items={state.hand} state={state} locked={locked} action={action} share />
        <h3>已经公开</h3><EvidenceGrid items={state.publicEvidence} state={state} locked={locked} action={action} /></>}
      {panel === "local" && <>{evidenceHere.length ? <EvidenceGrid items={evidenceHere.filter((item, index) => evidenceHere.findIndex(other => other.id === item.id) === index)} state={state} locked={locked} action={action} share />
        : <p>这里已经调查过，手边没有新的材料。可以去其他地点。</p>}</>}
      {panel === "log" && <NightLog state={state} narration={narration} />}
      {panel === "found" && <>{foundItems.map(item => <article key={item.id}><h3>{item.title}</h3><p>{item.detail}</p></article>)}
        <button onClick={() => { setFound([]); setPanel(null); }}>收好材料，回到故事</button></>}
    </SceneDialog>}
    {risk && <SceneDialog title={risk.label} onClose={() => setRisk(null)}>
      <p>{risk.description} 执行后需要当场应对门后的事。当前异常 {world.anomaly}/{world.anomalyLimit}。</p>
      <div className="scene-confirm"><button autoFocus onClick={() => setRisk(null)}>暂不行动</button>
        <button className="primary" disabled={locked} onClick={() => {
          action("act", { actionId: risk.id, confirm: true, version: risk.version }); setRisk(null);
        }}>打开门，面对现场</button></div>
    </SceneDialog>}
    {deathActive && <DeathSequence cause={deathActive}
      background={deathActive === "sealed" ? SCENES.exit.image : scene.image}
      soundEnabled={soundEnabled} toggleSound={toggleSound} playSound={deathSound.play}
      stopSound={deathSound.stop} onComplete={finishDeath} />}
  </main>;
}

function isServiceDefault(img) {
  // Verified generation-service fallback is a 1832px square; art uses other ratios.
  return img.naturalWidth === 1832 && img.naturalHeight === 1832;
}

function Destination({ state, locationId, locked, execute, search }) {
  const location = state.locations.find(item => item.id === locationId);
  const scene = SCENES[locationId];
  return <section className="map-destination"><h3>{location.name}</h3><p>{location.description}</p>
    {!location.searched && <button className="primary" disabled={locked || !location.available} onClick={() => search(locationId)}>
      前往{location.name}，{scene.search} · 30分钟</button>}
    <div className="scene-local-actions">{sceneActions(state, locationId).map(item => <button key={item.id}
      disabled={locked || !item.available} onClick={() => execute(item)}><span>{item.label}
        {item.reasons.length > 0 && <em>{item.reasons.join("；")}</em>}</span>
        <small>{item.dangerous ? "冒险" : item.cost === 0 ? "不耗时" : "30分钟"}</small></button>)}</div>
    {location.searched && sceneActions(state, locationId).length === 0 && <p className="muted">这里暂时没有新的行动。已取得的材料保存在随身线索中。</p>}
  </section>;
}

function SceneDialog({ title, onClose, children }) {
  const dialog = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialog.current?.focus();
    return () => { document.body.style.overflow = oldOverflow; previous?.focus(); };
  }, []);
  return <div className="dialog-backdrop scene-dialog-backdrop" onClick={onClose}>
    <section className="scene-notebook" role="dialog" aria-modal="true" aria-label={title} ref={dialog} tabIndex={-1}
      onClick={event => event.stopPropagation()} onKeyDown={event => {
        if (event.key === "Escape") onClose();
        if (event.key === "Tab") {
          const focusable = [...dialog.current.querySelectorAll("button:not(:disabled),a[href],textarea:not(:disabled),summary,[tabindex='0']")];
          const first = focusable[0], last = focusable.at(-1);
          if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) { event.preventDefault(); last?.focus(); }
          else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog.current)) { event.preventDefault(); first?.focus(); }
        }
      }}>
      <header><div><span className="eyebrow">随身笔记 · 阅读不耗时</span><h2>{title}</h2></div><button onClick={onClose}>回到现场 ×</button></header>
      {children}
    </section>
  </div>;
}

function DungeonEnding({ state, action, narration, replay }) {
  const { world, result } = state;
  return <section className="dungeon-panel scene-ending" id="dungeon-ending" tabIndex={-1}>
    <span className="eyebrow">本局结局 / {result.id === "failure" ? "未通关" : "已通关"}</span>
    <h2>{result.title}</h2><p>{result.reason}</p>
    {result.id === "failure" && <button className="scene-ending-replay" onClick={replay}>重看最后一幕</button>}
    <div className="dungeon-objectives"><span>{world.flags.sisterRescued ? "✓" : "◇"} 带回许宁</span>
      <span>{world.flags.nameRecorded ? "✓" : "◇"} 登记周槐实名</span>
      <span>{world.flags.powerRestored && world.flags.debrisCleared ? "✓" : "◇"} 清除巡查危险</span></div>
    <h3>这一夜的真相</h3><p>{result.truth}</p>
    <p>本轮许宁在 {result.variant.roomNumber} 病房，腕带为{result.variant.bracelet}，安全回路为 {result.variant.breaker}。</p>
    {result.rules.map(rule => <details key={rule.id}><summary>{rule.text}</summary><p>{rule.truth}</p></details>)}
    <h3>人物的隐瞒与利益</h3>
    {result.characters.map(person => <details key={person.id}><summary>{person.name} · {person.role}</summary>
      <p>{person.private_secret}</p><ul>{person.facts.map(fact => <li key={fact}>{fact}</li>)}</ul></details>)}
    <details><summary>全部材料，包括未发现的线索</summary><EvidenceGrid items={result.evidence} state={state} locked action={action} /></details>
    <details><summary>本局行动记录</summary><NightLog state={state} narration={narration} /></details>
  </section>;
}

function NightLog({ state, narration }) {
  return <div className="dungeon-log">{state.board.map(entry => <article key={entry.id}>
    <span className="eyebrow">{entry.speakerId === "host" ? "夜班记录" : entry.speakerName}</span>
    <p>{entry.speakerId === "host" ? entry.text : narration.replyText(`${state.case.id}:board-${entry.id}`, entry.text)}</p>
    {entry.evidenceIds.length > 0 && <small>公开材料：{entry.evidenceIds.map(id => state.publicEvidence.find(e => e.id === id)?.title || id).join("、")}</small>}
  </article>)}</div>;
}
