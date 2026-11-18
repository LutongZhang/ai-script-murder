import { useCallback, useEffect, useRef } from "react";

export function useDeathSound(enabled, scene = {}) {
  const context = useRef(null);
  const sources = useRef([]);
  const ambient = useRef(null);
  const enabledRef = useRef(enabled);
  const sceneRef = useRef(scene);
  enabledRef.current = enabled;
  sceneRef.current = scene;

  const stopAmbient = useCallback(() => {
    const current = ambient.current;
    if (!current) return;
    clearInterval(current.timer);
    current.nodes.forEach(node => {
      try { node.stop?.(); } catch { /* Already stopped. */ }
      node.disconnect();
    });
    ambient.current = null;
  }, []);

  const refreshAmbient = useCallback(() => {
    stopAmbient();
    const audio = context.current;
    const current = sceneRef.current;
    if (!enabledRef.current || current.ended || audio?.state !== "running") return;
    const hum = audio.createOscillator();
    hum.frequency.value = current.location === "power" ? 100 : 60;
    const volume = audio.createGain();
    volume.gain.value = current.night ? .0025 : .004;
    hum.connect(volume).connect(audio.destination);
    hum.start();
    const nodes = [hum, volume];
    let timer;
    if (current.danger) {
      const step = () => {
        if (document.hidden) return;
        const now = audio.currentTime;
        for (let i = 0; i < 3; i++) {
          const foot = audio.createOscillator();
          foot.frequency.setValueAtTime(72, now + i * .68);
          foot.frequency.exponentialRampToValueAtTime(32, now + i * .68 + .18);
          const gain = audio.createGain();
          gain.gain.setValueAtTime(0, now + i * .68);
          gain.gain.linearRampToValueAtTime(.024, now + i * .68 + .025);
          gain.gain.exponentialRampToValueAtTime(.0001, now + i * .68 + .21);
          const pan = audio.createStereoPanner?.();
          foot.connect(gain);
          if (pan) { pan.pan.value = i % 2 ? -.35 : .35; gain.connect(pan).connect(audio.destination); }
          else gain.connect(audio.destination);
          foot.start(now + i * .68); foot.stop(now + i * .68 + .23);
          nodes.push(foot, gain, ...(pan ? [pan] : []));
          foot.onended = () => {
            [foot, gain, pan].filter(Boolean).forEach(node => {
              node.disconnect();
              const at = nodes.indexOf(node);
              if (at >= 0) nodes.splice(at, 1);
            });
          };
        }
      };
      step();
      timer = setInterval(step, 3400);
    }
    ambient.current = { nodes, timer };
  }, [stopAmbient]);

  const stop = useCallback(() => {
    sources.current.forEach(source => {
      try { source.stop(); } catch { /* The short sound may already have ended. */ }
      source.disconnect();
    });
    sources.current = [];
  }, []);

  const unlock = useCallback(() => {
    const Audio = window.AudioContext || window.webkitAudioContext;
    if (!Audio) return;
    try {
      context.current ||= new Audio();
      if (context.current.state === "suspended") context.current.resume().then(refreshAmbient).catch(() => {});
      else if (!ambient.current) refreshAmbient();
    } catch { /* The visual sequence also works without browser audio. */ }
  }, [refreshAmbient]);

  useEffect(() => {
    document.addEventListener("pointerdown", unlock, { passive: true });
    document.addEventListener("keydown", unlock);
    return () => {
      document.removeEventListener("pointerdown", unlock);
      document.removeEventListener("keydown", unlock);
      stop();
      stopAmbient();
      context.current?.close().catch(() => {});
      context.current = null;
    };
  }, [unlock, stop, stopAmbient]);
  useEffect(() => { if (!enabled) stop(); }, [enabled, stop]);
  useEffect(refreshAmbient, [enabled, scene.location, scene.night, scene.danger, scene.ended, refreshAmbient]);

  const play = useCallback(cause => {
    const audio = context.current;
    if (!enabledRef.current || audio?.state !== "running") return;
    stop();
    const now = audio.currentTime;
    const buffer = audio.createBuffer(1, Math.ceil(audio.sampleRate * .85), audio.sampleRate);
    const samples = buffer.getChannelData(0);
    for (let i = 0; i < samples.length; i++) samples[i] = Math.random() * 2 - 1;
    const noise = audio.createBufferSource();
    noise.buffer = buffer;
    const filter = audio.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.setValueAtTime(cause === "caught" ? 1800 : 650, now);
    filter.frequency.exponentialRampToValueAtTime(100, now + .8);
    const gain = audio.createGain();
    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(.07, now + .025);
    gain.gain.exponentialRampToValueAtTime(.001, now + .8);
    noise.connect(filter).connect(gain).connect(audio.destination);
    const bass = audio.createOscillator();
    bass.frequency.setValueAtTime(cause === "caught" ? 82 : 60, now);
    bass.frequency.exponentialRampToValueAtTime(27, now + .75);
    const bassGain = audio.createGain();
    bassGain.gain.setValueAtTime(0, now);
    bassGain.gain.linearRampToValueAtTime(.06, now + .03);
    bassGain.gain.exponentialRampToValueAtTime(.001, now + .75);
    bass.connect(bassGain).connect(audio.destination);
    sources.current = [noise, bass];
    noise.start(now); bass.start(now);
    noise.stop(now + .85); bass.stop(now + .85);
    noise.onended = () => { noise.disconnect(); filter.disconnect(); gain.disconnect(); };
    bass.onended = () => { bass.disconnect(); bassGain.disconnect(); };
  }, [stop]);

  return { play, stop };
}
