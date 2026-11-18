import { useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ART } from "../hooks/dungeonArt.js";
import "./DeathSequence.css";

export function DeathSequence({ cause, background, soundEnabled, toggleSound, playSound, stopSound, onComplete }) {
  const [phase, setPhase] = useState("approach");
  const [monsterReady, setMonsterReady] = useState(false);
  const [backgroundReady, setBackgroundReady] = useState(false);
  const dialog = useRef(null);
  const caught = cause === "caught";

  useLayoutEffect(() => {
    const previous = document.activeElement;
    const oldOverflow = document.body.style.overflow;
    const backgroundNodes = [...document.body.children].filter(node => node !== dialog.current);
    const previousInert = backgroundNodes.map(node => node.inert);
    backgroundNodes.forEach(node => { node.inert = true; });
    document.body.style.overflow = "hidden";
    dialog.current?.focus();
    const timers = [
      window.setTimeout(() => { setPhase("impact"); playSound(cause); }, 1900),
      window.setTimeout(() => setPhase("blackout"), 2600),
      window.setTimeout(() => setPhase("title"), 3100),
      window.setTimeout(onComplete, 4700),
    ];
    return () => {
      timers.forEach(timer => window.clearTimeout(timer));
      stopSound();
      document.body.style.overflow = oldOverflow;
      backgroundNodes.forEach((node, index) => { node.inert = previousInert[index]; });
      if (previous?.isConnected) previous.focus({ preventScroll: true });
    };
  }, [cause, playSound, stopSound, onComplete]);

  return createPortal(<section ref={dialog} tabIndex={-1}
    className={`death-sequence death-${cause} death-${phase}`} role="dialog" aria-modal="true"
    aria-label={caught ? "失败演出：无脸巡查员逼近" : "失败演出：出口关闭"}
    onKeyDown={event => {
      if (event.key === "Escape") { event.stopPropagation(); onComplete(); }
      if (event.key === "Tab") {
        const buttons = [...dialog.current.querySelectorAll("button")];
        const first = buttons[0], last = buttons.at(-1);
        if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) {
          event.preventDefault(); last.focus();
        } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog.current)) {
          event.preventDefault(); first.focus();
        }
      }
    }}>
    <div className="death-stage" aria-hidden="true">
      <img className={`death-background${backgroundReady ? " is-ready" : ""}`} src={background} alt=""
        onLoad={event => setBackgroundReady(isGenerated(event.currentTarget))} />
      <div className="death-shadow" />
      {caught ? <img className={`death-monster${monsterReady ? " is-ready" : ""}`} src={ART.patrol} alt=""
        onLoad={event => setMonsterReady(isGenerated(event.currentTarget))} />
        : <div className="death-doors"><span /><span /></div>}
      <div className="death-black" />
    </div>
    <div className="death-controls"><button aria-pressed={soundEnabled} onClick={toggleSound}>音效{soundEnabled ? "开" : "关"}</button>
      <button onClick={onComplete}>跳过演出 · Esc</button></div>
    <p className="death-caption">{phase === "impact" ? (caught ? "来不及了。" : "最后一道门闭合了。")
      : caught ? "走廊尽头，有东西在靠近。" : "机械钟走到了 07:00。门后最后一点光正在消失。"}</p>
    <div className="death-last-line" aria-live="polite" aria-hidden={phase !== "title"}><span>{caught ? "你的影子，比你先一步停下。" : "这一次，门没有再打开。"}</span>
      <h2>留在第七夜</h2></div>
  </section>, document.body);
}

function isGenerated(img) {
  return !(img.naturalWidth === 1832 && img.naturalHeight === 1832);
}
