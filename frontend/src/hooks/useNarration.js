import { useEffect, useRef, useState } from "react";
import { characterStyle, chineseVoices, chooseVoice, delivery, SpeechPlayer, voiceKey } from "./characterVoice.js";

const SETTINGS_KEY = "script-kill.character-voices";

export function useNarration() {
  const [animation, setAnimation] = useState(null);
  const [visibleLength, setVisibleLength] = useState(0);
  const [voice, setVoice] = useState(false);
  const voiceRef = useRef(false);
  const supported = "speechSynthesis" in window;
  const [voices, setVoices] = useState([]);
  const [settings, setSettings] = useState(() => {
    try {
      const value = JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}");
      return value && typeof value === "object" && !Array.isArray(value) ? value : {};
    } catch { return {}; }
  });
  const voicesRef = useRef([]);
  const settingsRef = useRef(settings);
  const lastReplies = useRef({});
  const playerRef = useRef(null);
  if (supported && !playerRef.current) {
    playerRef.current = new SpeechPlayer(window.speechSynthesis, window.SpeechSynthesisUtterance);
  }

  useEffect(() => {
    if (!supported) return;
    function loadVoices() {
      voicesRef.current = chineseVoices(window.speechSynthesis.getVoices());
      setVoices(voicesRef.current);
    }
    loadVoices();
    window.speechSynthesis.addEventListener("voiceschanged", loadVoices);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", loadVoices);
  }, [supported]);

  useEffect(() => {
    if (!animation) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setAnimation(null);
      return;
    }
    const timer = window.setInterval(() => setVisibleLength((length) => {
      if (length >= animation.text.length) {
        window.clearInterval(timer);
        return length;
      }
      return Math.min(length + 2, animation.text.length);
    }), 25);
    return () => window.clearInterval(timer);
  }, [animation]);

  useEffect(() => () => { playerRef.current?.stop(); }, []);

  function clear() {
    setAnimation(null);
    playerRef.current?.stop();
    lastReplies.current = {};
  }

  function speak(text, speaker) {
    const style = characterStyle(speaker);
    const saved = settingsRef.current[voiceKey(speaker)] || {};
    playerRef.current?.enqueue(text, {
      voice: chooseVoice(voicesRef.current, style, saved.voiceURI),
      ...delivery(style, speaker.emotion, saved.rate),
    });
  }

  function showReply(key, text, speaker = {}) {
    setAnimation({ key, text });
    setVisibleLength(0);
    lastReplies.current[voiceKey(speaker)] = { text, speaker };
    if (voiceRef.current && supported) speak(text, speaker);
  }

  function toggleVoice() {
    voiceRef.current = !voiceRef.current;
    setVoice(voiceRef.current);
    if (!voiceRef.current) playerRef.current?.stop();
  }

  function configure(speaker, change) {
    const key = voiceKey(speaker);
    const updated = { ...settingsRef.current, [key]: { ...settingsRef.current[key], ...change } };
    settingsRef.current = updated;
    setSettings(updated);
    try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(updated)); } catch { /* Optional storage. */ }
  }

  function preview(speaker) {
    const reply = lastReplies.current[voiceKey(speaker)];
    if (!reply) return;
    playerRef.current?.stop();
    speak(reply.text, reply.speaker);
  }

  function replyText(key, text) {
    return animation?.key === key ? text.slice(0, visibleLength) : text;
  }

  return { voice, supported, toggleVoice, showReply, replyText, clear, visibleLength,
    voices, settings, configure, preview, canPreview: (speaker) => Boolean(lastReplies.current[voiceKey(speaker)]),
    stopSpeech: () => playerRef.current?.stop() };
}
