import { useState } from "react";
import { BookPanel } from "./BookPanel.jsx";
import { PrivateChat } from "./PrivateChat.jsx";
import { SearchPanel } from "./SearchPanel.jsx";
import { TablePanel } from "./TablePanel.jsx";
import { PrivateInvitations } from "./PrivateInvitations.jsx";
import { AccusationReminder } from "./AccusationReminder.jsx";

function phaseTab(state) {
  return ({ reading: "book", exchange: "private", search: "search" })[state.phaseKind] || "table";
}

export function GameWorkspace({ game, narration }) {
  const { state, busy, action, privateErrors, resumeTurns } = game;
  const [tab, setTab] = useState(phaseTab(state));
  const [selectedNpc, setSelectedNpc] = useState(state.npcs[0].id);
  const [confirmAccusation, setConfirmAccusation] = useState(false);
  const pending = state.pendingSpeakers.length > 0;
  const locked = Boolean(busy || pending);
  const props = { state, busy, locked, action, privateErrors, narration, selectedNpc, setSelectedNpc };
  const tabs = [
    ["book", "我的剧本", "身份 · 经历 · 个人目标"],
    ["private", "单独聊聊", `${state.npcs.length} 位角色，独立对话`],
    ["search", state.phaseKind === "discussion" && state.allowedActions.includes("search") ? "去补查" : "去搜证",
      state.allowedActions.includes("search") ? `本阶段剩余 ${state.searchesLeft} 次` : "本阶段未开放"],
    ["table", state.phaseKind === "reveal" ? "投票与复盘" : "回到桌上", "公共讨论 · 公开线索"],
  ];
  return <main className="game">
    <section className="round-header"><div>
      <span className="eyebrow">{state.case.title} / {state.playMode === "killer" ? "凶手模式 / " : ""}你是 {state.player.name} · {state.player.role}</span>
      <h1>{state.phaseLabel}<span>第 {state.phase} 幕</span></h1><p>{state.objective}</p></div>
      {state.nextPhase && <button className="primary" disabled={locked}
        onClick={() => {
          if (state.nextPhase.kind === "accusation") setConfirmAccusation(true);
          else action("advance", {}, (data) => setTab(phaseTab(data)));
        }}>
        进入{state.nextPhase.label} →</button>}
    </section>
    <ol className="phase-track">{state.phases.map((label, index) => <li key={state.case.mode.phases[index].id}
      className={index + 1 === state.phase ? "current" : index + 1 < state.phase ? "complete" : ""}
      aria-current={index + 1 === state.phase ? "step" : undefined}>
      <span>{index + 1 < state.phase ? "✓" : `0${index + 1}`}</span>{label}</li>)}</ol>
    <div className="workspace">
      <aside className="sidebar">
        <div className="your-seat"><span className="eyebrow">你的席位</span><h2>{state.player.name}</h2><p>{state.player.role} · 由你扮演</p></div>
        <nav aria-label="游戏区域">{tabs.map(([id, title, subtitle]) => <button key={id} className={tab === id ? "active" : ""}
          aria-current={tab === id ? "page" : undefined} onClick={() => setTab(id)}>{title}<span>{subtitle}</span></button>)}</nav>
        <div className="seated"><span className="eyebrow">与你同桌</span>{state.npcs.map((person, index) => <div className="seated-person" key={person.id}>
          <span className={`mini-avatar seat-${index % 4}`}>{person.name[0]}</span>
          <span>{person.name}<small>{person.role}</small></span><span className="ai-badge">AI</span>
        </div>)}</div>
      </aside>
      <section className="main-panel">
        {busy && <div className="status" role="status"><span className="spinner" />{busy}</div>}
        {pending && !busy && <div className="resume"><p>{state.phaseKind === "accusation" ? "还有角色尚未完成指认。" : "还有角色等待发言。"}继续后将从当前角色接上。</p>
          <button className="primary" onClick={resumeTurns}>继续{state.phaseKind === "accusation" ? "指认" : "AI 发言"}</button></div>}
        {game.initiativeError && state.allowedActions.includes("initiative") && <div className="resume" role="alert">
          <p>主动私聊暂未完成：{game.initiativeError}</p>
          <button disabled={locked} onClick={game.assessInitiative}>重试邀约判断</button>
        </div>}
        <PrivateInvitations invitations={state.privateInvitations} disabled={locked}
          onRespond={(invitation, decision) => action("invitation-response", { invitationId: invitation.id, decision }, () => {
            if (decision === "accept") { setSelectedNpc(invitation.npcId); setTab("private"); }
          })} />
        <div hidden={tab !== "book"}><BookPanel {...props} /></div>
        <div hidden={tab !== "private"}><PrivateChat {...props} /></div>
        <div hidden={tab !== "search"}><SearchPanel {...props} /></div>
        <div hidden={tab !== "table"}><TablePanel {...props} onSearch={() => setTab("search")} /></div>
      </section>
    </div>
    {confirmAccusation && state.nextPhase?.kind === "accusation" && <AccusationReminder
      readiness={state.accusationReadiness} nextLabel={state.nextPhase.label} locked={locked}
      onContinue={() => setConfirmAccusation(false)}
      onConfirm={() => action("advance", { confirmAccusation: true }, (data) => {
        setConfirmAccusation(false); setTab(phaseTab(data));
      })} />}
  </main>;
}
