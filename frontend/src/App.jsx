import { useEffect, useState } from "react";
import { useGame } from "./hooks/useGame.js";
import { useNarration } from "./hooks/useNarration.js";
import { ScriptLibrary } from "./components/ScriptLibrary.jsx";
import { RoleLobby } from "./components/RoleLobby.jsx";
import { GameWorkspace } from "./components/GameWorkspace.jsx";
import { DungeonWorkspace } from "./components/DungeonWorkspace.jsx";
import { VoiceSettings } from "./components/VoiceSettings.jsx";

export default function App() {
  const narration = useNarration();
  const game = useGame(narration.showReply);
  const { state, screen, busy, error } = game;
  const [confirmReset, setConfirmReset] = useState(false);
  const [voiceSettings, setVoiceSettings] = useState(false);
  const theme = screen === "library" ? "library" : state?.case.theme || "rain";

  useEffect(() => {
    document.title = screen === "library" ? "局中人 | AI 叙事副本" : `${state?.case.title || "局中人"} | AI 叙事副本`;
  }, [screen, state?.case.title]);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [screen, state?.case.id, state?.player?.id]);

  function openLibrary() {
    narration.clear();
    game.openLibrary();
  }

  function selectScript(id) {
    narration.clear();
    game.selectScript(id);
  }

  return <div className={`app theme-${theme}${screen === "game" && state?.case.gameType === "dungeon" ? " is-visual-novel" : ""}`}>
    {theme === "rain" && <div className="rain" aria-hidden="true" />}
    <div className="ambient" aria-hidden="true" />
    <header className="topbar">
      <button className="brand" disabled={Boolean(busy)} onClick={openLibrary}>局中人<span>AI 叙事副本</span></button>
      <div className="header-actions">
        <span className="live-dot" /><span>一人入局 · AI 同桌</span>
        {screen !== "library" && <button disabled={Boolean(busy)} onClick={openLibrary}>剧本库</button>}
        {narration.supported && <button aria-pressed={narration.voice} onClick={narration.toggleVoice}>语音{narration.voice ? "开" : "关"}</button>}
        {narration.supported && state && screen !== "library" && <button onClick={() => setVoiceSettings(true)}>人物声音</button>}
        {state?.player && screen === "game" && <button disabled={Boolean(busy)} onClick={() => setConfirmReset(true)}>重开本剧本</button>}
      </div>
    </header>

    {error && <div className="error" role="alert">{error}
      {!state && <button onClick={() => window.location.reload()}>重新连接</button>}
    </div>}
    {!state && <div className="loading">{error ? "暂时无法连接剧本库。" : "正在打开故事陈列室…"}</div>}
    {state && screen === "library" && <>
      {busy && <div className="library-status status" role="status"><span className="spinner" />{busy}</div>}
      <ScriptLibrary scripts={game.scripts} busy={busy} onSelect={selectScript} />
    </>}
    {state && screen === "lobby" && <RoleLobby state={state} busy={busy}
      onBack={openLibrary} onStart={(roleId) => game.action("start", { roleId })}
      onStartKiller={() => game.action("start-killer")} />}
    {state?.player && screen === "game" && (state.case.gameType === "dungeon"
      ? <DungeonWorkspace key={`${state.case.id}:${state.player.id}`} game={game} narration={narration} />
      : <GameWorkspace key={`${state.case.id}:${state.player.id}`} game={game} narration={narration} />)}

    {voiceSettings && state && <VoiceSettings state={state} narration={narration} onClose={() => setVoiceSettings(false)} />}
    {confirmReset && <div className="dialog-backdrop" onClick={() => setConfirmReset(false)}>
      <section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="reset-title"
        onClick={(event) => event.stopPropagation()} onKeyDown={(event) => {
          if (event.key === "Escape") setConfirmReset(false);
        }}>
        <span className="eyebrow">重新入局</span><h2 id="reset-title">重开《{state.case.title}》？</h2>
        <p>本剧本的进度、聊天和线索会清空。其他剧本的进度继续保留。</p>
        <div><button autoFocus onClick={() => setConfirmReset(false)}>继续当前局</button>
          <button className="primary" onClick={() => {
            setConfirmReset(false); narration.clear(); game.action("reset");
          }}>确认重开</button></div>
      </section>
    </div>}
    <footer className="site-footer">每个人说的话，都只是故事的一部分。</footer>
  </div>;
}
