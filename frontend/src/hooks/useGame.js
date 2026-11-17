import { useEffect, useRef, useState } from "react";
import { getState, request } from "../api.js";

const STORAGE_KEY = "script-kill.selected-script";

export function useGame(onReply) {
  const [state, setState] = useState(null);
  const [scripts, setScripts] = useState([]);
  const [screen, setScreen] = useState("library");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [privateErrors, setPrivateErrors] = useState({});
  const [initiativeError, setInitiativeError] = useState("");
  const busyRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const catalog = await request("scripts");
        let saved;
        try { saved = localStorage.getItem(STORAGE_KEY); } catch { /* Storage is optional. */ }
        const id = catalog.scripts.some((script) => script.id === saved) ? saved : catalog.defaultScriptId;
        const data = await getState(id);
        if (cancelled) return;
        setScripts(catalog.scripts);
        setState(data);
        setScreen(data.player ? "game" : "library");
      } catch (err) { if (!cancelled) setError(err.message); }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  function saveState(data) {
    setState(data);
    setScripts((old) => old.map((script) => script.id === data.case.id ? {
      ...script, progress: {
        started: Boolean(data.player), phase: data.phase,
        phaseLabel: data.phaseLabel, playerName: data.player?.name || null,
      },
    } : script));
  }

  async function selectScript(id) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy("正在打开剧本…");
    setError("");
    try {
      const data = await getState(id);
      saveState(data);
      setInitiativeError("");
      try { localStorage.setItem(STORAGE_KEY, id); } catch { /* Storage is optional. */ }
      setScreen(data.player ? "game" : "lobby");
    } catch (err) { setError(err.message); }
    finally { setBusy(""); busyRef.current = false; }
  }

  async function completeTurns(data) {
    let current = data;
    while (current.pendingSpeakers.length) {
      const person = current.roles.find((role) => role.id === current.pendingSpeakers[0]);
      setBusy(current.phaseKind === "accusation" ? `${person.name}正在秘密指认…` : `${person.name}正在斟酌发言…`);
      const response = await request("ai-turn", { scriptId: current.case.id });
      current = response.state;
      saveState(current);
      if (response.reply) onReply(`${current.case.id}:board-${current.board.at(-1).id}`, response.reply,
        { ...current.roles.find((role) => role.id === current.board.at(-1).speakerId), scriptId: current.case.id });
    }
  }

  async function action(path, body = {}, onSuccess) {
    if (busyRef.current || !state) return;
    const scriptId = state.case.id;
    const errorKey = `${scriptId}:${body.npcId}`;
    busyRef.current = true;
    setBusy(path === "question" ? "对方正在思考，私聊只在你们之间进行…" : "正在处理…");
    setError("");
    if (path === "question") setPrivateErrors((old) => ({ ...old, [errorKey]: "" }));
    try {
      const response = await request(path, { ...body, scriptId });
      const data = response.state || response;
      saveState(data);
      if (path === "start" || path === "start-killer") setScreen("game");
      if (path === "reset") {
        setScreen("lobby");
        setInitiativeError("");
        setPrivateErrors((old) => Object.fromEntries(Object.entries(old).filter(([key]) => !key.startsWith(`${scriptId}:`))));
      }
      onSuccess?.(data);
      if (path === "question") {
        onReply(`${scriptId}:private-${body.npcId}-${data.privateChats[body.npcId].length - 1}`, response.reply,
          { ...data.roles.find((role) => role.id === body.npcId), scriptId });
      }
      if (path === "invitation-response" && body.decision === "accept" && response.reply) {
        const invitation = state.privateInvitations.find((item) => item.id === body.invitationId);
        onReply(`${scriptId}:private-${invitation.npcId}-${data.privateChats[invitation.npcId].length - 1}`, response.reply,
          { ...data.roles.find((role) => role.id === invitation.npcId), scriptId });
      }
      await completeTurns(data);
    } catch (err) {
      if (path === "question") setPrivateErrors((old) => ({ ...old, [errorKey]: err.message }));
      else setError(err.message);
      try { saveState(await getState(scriptId)); } catch { /* Keep last known state. */ }
    } finally { setBusy(""); busyRef.current = false; }
  }

  async function resumeTurns() {
    if (busyRef.current || !state) return;
    const scriptId = state.case.id;
    busyRef.current = true;
    setError("");
    try { await completeTurns(state); }
    catch (err) {
      setError(err.message);
      try { saveState(await getState(scriptId)); } catch { /* Keep last known state. */ }
    } finally { setBusy(""); busyRef.current = false; }
  }

  async function openLibrary() {
    if (busyRef.current) return;
    setScreen("library");
    try {
      const catalog = await request("scripts");
      setScripts(catalog.scripts);
    } catch (err) { setError(err.message); }
  }

  async function assessInitiative() {
    if (busyRef.current || !state?.allowedActions.includes("initiative")) return;
    busyRef.current = true;
    const scriptId = state.case.id;
    setBusy(`${state.initiativeQueue?.length || 0}位角色正在同时考虑是否找你私聊…`);
    setInitiativeError("");
    try {
      const response = await request("initiative", { scriptId });
      saveState(response.state);
      setInitiativeError((response.errors || []).map((item) => `${item.npcName}：${item.message}`).join("；"));
    } catch (err) {
      setInitiativeError(err.message);
      try { saveState(await getState(scriptId)); } catch { /* Keep last known state. */ }
    } finally { setBusy(""); busyRef.current = false; }
  }

  useEffect(() => {
    if (screen !== "game" || busy || initiativeError || !state ||
        !state.allowedActions.includes("initiative") || !state.initiativeQueue?.length ||
        state.pendingSpeakers.length || state.privateInvitations?.some((item) => item.status === "pending")) return;
    // Wait for a short idle gap; player actions cancel this scheduled assessment.
    const timer = window.setTimeout(() => {
      if (document.activeElement?.matches("textarea, input")) return;
      assessInitiative();
    }, 2500);
    return () => window.clearTimeout(timer);
  }, [state, screen, busy, initiativeError]);

  return { state, scripts, screen, busy, error, privateErrors, action,
    selectScript, openLibrary, resumeTurns, initiativeError, assessInitiative };
}
