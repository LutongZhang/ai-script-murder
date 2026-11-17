import { useEffect, useRef, useState } from "react";
import { EvidenceGrid } from "./EvidenceCard.jsx";
import { StoryReview } from "./StoryReview.jsx";

function VotePanel({ state, locked, action }) {
  const [vote, setVote] = useState("");
  return <div className="vote-panel"><h3>你的秘密指认</h3><p>一人一票，所有人完成后一起揭晓。提交后不能更改。</p>
    {state.playerVote ? <p className="voted">你已指认{state.roles.find((role) => role.id === state.playerVote)?.name}。等待其他人的选择。</p> : <>
      <div className="vote-options">{state.roles.map((role) => <button key={role.id} aria-pressed={vote === role.id}
        className={vote === role.id ? "selected" : ""} disabled={locked} onClick={() => setVote(role.id)}>
        {role.name}<small>{role.role}</small></button>)}</div>
      <button className="primary" disabled={locked || !vote} onClick={() => action("vote", { targetId: vote })}>提交指认</button>
    </>}
  </div>;
}

function ResultPanel({ result }) {
  return <div className="result-panel">
    {result.votes.length > 0 && <><h3>{result.accusedName ? `最终被指认：${result.accusedName}` : `平票：${result.tiedNames.join("、")}`}</h3>
    <p>{result.groupSolved ? "这一桌找到了真正的凶手。" : result.accusedName ? "这一桌的指认偏离了真相。" : "这一桌没有形成唯一指认。"}</p></>}
    <div className="vote-results">{result.votes.map((item) => <article key={item.voterId}>
      <strong>{item.voterName} → {item.targetName}</strong><p>{item.reason}</p></article>)}</div>
    <h3>你的个人目标</h3>{result.goals.map((goal) => <p className={goal.complete ? "goal-done" : "muted"} key={goal.title}>
      {goal.complete === null ? "◇ 自行回顾" : goal.complete ? "✓ 达成" : "○ 未达成"} · {goal.title}</p>)}
    <div className="secret"><h3>案件真相</h3><p>{result.truth}</p></div>
    <details><summary>完整案情时间线 · 仅复盘揭晓</summary>{result.timeline.map((event) => <p key={`${event.time}:${event.title}`}>
      <strong>{event.time} · {event.title}</strong><br />{event.detail}</p>)}</details>
    <StoryReview characters={result.characters} evidence={result.evidence} />
  </div>;
}

export function TablePanel({ state, locked, action, narration, onSearch }) {
  const [draft, setDraft] = useState("");
  const chatRef = useRef(null);
  const followup = state.phaseKind === "discussion" && state.allowedActions.includes("search");
  const followupLeft = Math.min(state.searchesLeft,
    state.locations.filter((location) => location.available && !location.searched).length);
  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [state.board, narration.visibleLength]);
  return <div className="table-panel">
    <span className="eyebrow">所有人同桌</span><h2>{state.phaseKind === "reveal" ? "故事，终于揭晓" : "把话说到桌面上"}</h2>
    {followup && <div className="resume" role="status">
      <p>{followupLeft > 0 ? `补查已开放 · 本阶段还能搜索 ${followupLeft} 个地点。`
        : "本阶段补查已完成，没有剩余可搜索的地点。"}
        {followupLeft > 0 && (state.pendingSpeakers.length > 0 ? "等本轮公聊结束后，去核对尚未搜索的地点。"
          : "去核对尚未搜索的地点，发现先放入你的手牌，再决定是否公开。")}</p>
      <button disabled={locked || !followupLeft} onClick={onSearch}>去补查 →</button>
    </div>}
    <details><summary>共同背景 · 已知的经过</summary>{state.case.timeline.map((event) => <p className="muted" key={event.title}>
      <strong>{event.time} · {event.title}</strong><br />{event.detail}</p>)}</details>
    {state.allowedActions.includes("vote") && <VotePanel state={state} locked={locked} action={action} />}
    {state.result && <ResultPanel result={state.result} />}
    <div className="board messages" ref={chatRef} aria-live="polite">{state.board.map((entry) => <article key={entry.id}
      className={`message ${entry.speakerId === "host" ? "host-message" : entry.speakerId === state.player.id ? "player-message" : ""}`}>
      <span>{entry.speakerName}{entry.speakerId === state.player.id ? " · 你" : ""}<small>第 {entry.phase} 幕</small></span>
      <p>{narration.replyText(`${state.case.id}:board-${entry.id}`, entry.text)}</p>
      {entry.evidenceIds.length > 0 && <div className="shared-clues">{entry.evidenceIds.map((id) => <span key={id}>
        公开：{state.publicEvidence.find((item) => item.id === id)?.title || id}</span>)}</div>}
    </article>)}</div>
    {state.allowedActions.includes("discuss") && <form className="composer" onSubmit={(event) => {
      event.preventDefault();
      if (!locked && draft.trim()) action("discuss", { message: draft }, () => setDraft(""));
    }}>
      <textarea aria-label="公开发言" maxLength={2000} value={draft} onChange={(event) => setDraft(event.target.value)}
        disabled={locked} placeholder="解释你的经历，回应某人，或者把怀疑放到桌面上…" />
      <div><button type="button" disabled={locked} onClick={() => action("discuss", { message: "" })}>听他们继续聊</button>
        <button className="primary" disabled={locked || !draft.trim()}>公开发言 ↗</button></div>
    </form>}
    <div className="section-title"><h3>全桌公开线索 · {state.publicEvidence.length}</h3><span>每个人都能据此发言和投票</span></div>
    <EvidenceGrid items={state.publicEvidence} state={state} locked={locked} action={action} />
    {state.allowedActions.includes("publish") && <details className="hand-on-table"><summary>从你的 {state.hand.length} 张手牌中选择公开</summary>
      <EvidenceGrid items={state.hand} state={state} locked={locked} action={action} share />
    </details>}
  </div>;
}
