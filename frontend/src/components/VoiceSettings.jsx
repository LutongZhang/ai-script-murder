import { characterStyle, chooseVoice, voiceKey } from "../hooks/characterVoice.js";

export function VoiceSettings({ state, narration, onClose }) {
  return <div className="dialog-backdrop" onClick={onClose}>
    <section className="confirm-dialog voice-dialog" role="dialog" aria-modal="true" aria-labelledby="voice-title"
      onClick={(event) => event.stopPropagation()} onKeyDown={(event) => {
        if (event.key === "Escape") onClose();
      }}>
      <button className="voice-close" autoFocus onClick={onClose} aria-label="关闭声音设置">关闭</button>
      <h2 id="voice-title">人物声音</h2>
      <p>为每个人挑一种声音。试听会重播该角色最近的发言，语音开关控制后续自动朗读。</p>
      {!narration.voices.length && <p role="status">暂未检测到中文声音。朗读会尝试使用系统默认中文声音；可在系统语音设置中添加中文音色。</p>}
      <div className="voice-roles">{state.npcs.map((npc) => {
        const speaker = { ...npc, scriptId: state.case.id };
        const style = characterStyle(speaker);
        const saved = narration.settings[voiceKey(speaker)] || {};
        const selected = chooseVoice(narration.voices, style, saved.voiceURI);
        return <div className="voice-role" key={npc.id}>
          <strong>{npc.name}<small>{style.label}</small></strong>
          <label>声音<select value={narration.voices.some((voice) => voice.voiceURI === saved.voiceURI) ? saved.voiceURI : ""} disabled={!narration.voices.length}
            onChange={(event) => narration.configure(speaker, { voiceURI: event.target.value })}>
            <option value="">自动选择{selected ? ` · ${selected.name}` : ""}</option>
            {narration.voices.map((voice) => <option key={voice.voiceURI} value={voice.voiceURI}>{voice.name} · {voice.lang}</option>)}
          </select></label>
          <label>语速 · {(saved.rate ?? style.rate).toFixed(2)}×
            <input type="range" min="0.8" max="1.15" step="0.01" value={saved.rate ?? style.rate}
              onChange={(event) => narration.configure(speaker, { rate: Number(event.target.value) })} /></label>
          <button disabled={!narration.canPreview(speaker)} onClick={() => narration.preview(speaker)}>试听最近发言</button>
        </div>;
      })}</div>
      <p>声音的自然程度取决于设备可用音色；仅一种中文声音时，人物主要通过节奏区分。</p>
      <div className="voice-footer"><button onClick={narration.stopSpeech}>停止朗读</button><button onClick={onClose}>完成</button></div>
    </section>
  </div>;
}
