import { useEffect, useRef, useState } from "react";

export function PrivateChat({ state, busy, locked, action, privateErrors, narration, selectedNpc, setSelectedNpc }) {
  const [drafts, setDrafts] = useState({});
  const chatRef = useRef(null);
  const npc = state.npcs.find((person) => person.id === selectedNpc) || state.npcs[0];
  const chats = state.privateChats[npc.id] || [];
  const canPrivate = state.allowedActions.includes("private");
  const error = privateErrors[`${state.case.id}:${npc.id}`];

  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [state, selectedNpc, narration.visibleLength, busy]);

  return <div className="conversation">
    <div className="chat-heading"><div><span className="eyebrow">私聊 · 只有你们两人听见</span>
      <h2>与{npc.name}单独聊聊</h2></div><span className="emotion">{npc.emotion}</span></div>
    <div className="npc-tabs">{state.npcs.map((person) => <button key={person.id} aria-pressed={npc.id === person.id}
      className={npc.id === person.id ? "active" : ""} onClick={() => setSelectedNpc(person.id)}>
      {person.name}<small>{person.role}</small></button>)}</div>
    <div className="messages" ref={chatRef} aria-live="polite">
      {!chats.length && <div className="empty-chat"><span>两个人，一场试探。</span>
        <p>可以交换经历、争取合作，也可以试探对方的秘密。</p><p>{npc.publicProfile}</p></div>}
      {chats.map((turn, index) => <div className="turn" key={`${npc.id}-${index}`}>
        {turn.question && <article className="message player-message"><span>{state.player.name} · 你</span><p>{turn.question}</p></article>}
        <article className="message"><span>{npc.name}{turn.initiator === "npc" ? " · 主动找你私聊" : ""}</span>
          <p>{narration.replyText(`${state.case.id}:private-${npc.id}-${index}`, turn.response)}</p>
          {turn.evidenceIds?.length > 0 && <div className="shared-clues">{turn.evidenceIds.map((id) => <span key={id}>
            私下交给你：{state.hand.find((item) => item.id === id)?.title || id} · 已放入我的剧本
          </span>)}</div>}
        </article>
      </div>)}
    </div>
    <form className="composer" onSubmit={(event) => {
      event.preventDefault();
      if (!locked && canPrivate && drafts[npc.id]?.trim()) {
        const npcId = npc.id;
        action("question", { npcId, question: drafts[npcId] },
          () => setDrafts((old) => ({ ...old, [npcId]: "" })));
      }
    }}>
      {error && <div className="private-error" role="alert"><strong>私聊未成功</strong><p>{error}</p><p>本轮未保存，你的输入仍在，可以重试。</p></div>}
      <textarea aria-label={`给${npc.name}的私聊`} maxLength={2000} value={drafts[npc.id] || ""}
        onChange={(event) => setDrafts((old) => ({ ...old, [npc.id]: event.target.value }))}
        placeholder={canPrivate ? "以你的角色开口，说些什么…" : "当前阶段未开放私聊。"} disabled={!canPrivate || Boolean(busy)} />
      <div><span>这段话不会自动公开给其他人</span>
        <button className="primary" disabled={locked || !canPrivate || !drafts[npc.id]?.trim()}>
          {error ? "重试私聊 ↗" : "发送私聊 ↗"}</button></div>
    </form>
  </div>;
}
