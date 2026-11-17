export function PrivateInvitations({ invitations, disabled, onRespond }) {
  if (!invitations?.length) return null;
  return <section className="private-invitations" aria-label="收到的私聊邀约" aria-live="polite">
    {invitations.map((invitation) => <article className="invitation-card" key={invitation.id}>
      <div className="invitation-heading"><span className="eyebrow">有人想找你单独聊聊</span>
        {invitation.status === "deferred" && <span className="muted">已暂缓 · 随时可以回应</span>}</div>
      <h3>{invitation.npcName}的邀约</h3><p>{invitation.message}</p>
      <div className="invitation-actions">
        <span>仅你可见 · 接受后由对方先开口</span>
        <button disabled={disabled} onClick={() => onRespond(invitation, "decline")}>婉拒</button>
        {invitation.status !== "deferred" && <button disabled={disabled}
          onClick={() => onRespond(invitation, "later")}>稍后回复</button>}
        <button className="primary" disabled={disabled} onClick={() => onRespond(invitation, "accept")}>接受私聊 ↗</button>
      </div>
    </article>)}
  </section>;
}
