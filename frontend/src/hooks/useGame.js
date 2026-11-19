import { useEffect, useRef, useState } from "react";
import { getState, request } from "../api.js";

const STORAGE_KEY = "script-kill.selected-script";

export function useGame(onReply) {
  const [state, setState] = useState(null);
  const [scripts, setScripts] = useState([]);
  const [screen, setScreen] = useState("library");
  const [busy, setBusy] = useState("");
  const [busyHint, setBusyHint] = useState("");
  const [error, setError] = useState("");
  const [privateErrors, setPrivateErrors] = useState({});
  const [initiativeError, setInitiativeError] = useState("");
  const busyRef = useRef(false);
  const waitTimer = useRef(null);

  useEffect(() => () => window.clearTimeout(waitTimer.current), []);

  function beginBusy(message, hint = "请求仍在处理中，并未取消。请求结束前不能重复提交；已有材料与谈话仍可阅读。") {
    window.clearTimeout(waitTimer.current);
    setBusy(message);
    setBusyHint("");
    waitTimer.current = window.setTimeout(() => setBusyHint(hint), 10000);
  }

  function endBusy() {
    window.clearTimeout(waitTimer.current);
    setBusy("");
    setBusyHint("");
    busyRef.current = false;
  }

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
    beginBusy("正在打开剧本…");
    setError("");
    try {
      const data = await getState(id);
      saveState(data);
      setInitiativeError("");
      try { localStorage.setItem(STORAGE_KEY, id); } catch { /* Storage is optional. */ }
      setScreen(data.player ? "game" : "lobby");
    } catch (err) { setError(err.message); }
    finally { endBusy(); }
  }

  async function completeTurns(data) {
    let current = data;
    while (current.pendingSpeakers.length || current.sceneCue) {
      const cue = current.sceneCue;
      const person = current.roles.find((role) => role.id === (cue?.npcId || current.pendingSpeakers[0]));
      const speech = cue?.kind === "speech";
      beginBusy(current.case.gameType === "dungeon"
        ? speech ? `${person.name}正在斟酌你的话，本次交谈尚未完成…`
          : `本次现场结果已保存，${person.name}正在斟酌回应…`
        : current.phaseKind === "accusation" ? `${person.name}正在秘密指认…` : `${person.name}正在斟酌发言…`,
      "真实人物回复仍在生成，请求并未取消。你可以阅读已取得材料与已有谈话、试听已有发言；改变现场或重试需等本次请求结束。失败后只接续未完成的回复，不重做已保存行动，也不额外扣时。");
      const response = await request(cue ? "scene-turn" : "ai-turn",
        { scriptId: current.case.id, ...(cue ? { cueId: cue.id } : {}) });
      current = response.state;
      saveState(current);
      if (response.reply) onReply(response.replyKey || `${current.case.id}:board-${current.board.at(-1).id}`, response.reply,
        { ...current.roles.find((role) => role.id === (response.speakerId || current.board.at(-1).speakerId)), scriptId: current.case.id });
    }
    return current;
  }

  async function action(path, body = {}, onSuccess) {
    if (busyRef.current || !state) return;
    const scriptId = state.case.id;
    const errorKey = `${scriptId}:${body.npcId}`;
    busyRef.current = true;
    beginBusy(path === "question" ? "对方正在斟酌你的话，本次交谈尚未完成…"
      : path === "scene-action" ? "正在理解你的行动，尚未执行…"
      : path === "choice" || path === "act" || path === "search" || path === "approach"
        ? "正在提交现场操作，尚未确认结果…" : "正在处理…",
    path === "scene-action"
      ? "动作请求仍在处理中，页面尚未收到执行结果。你可以阅读随身材料与已有谈话；请求结束前不能再提交行动或重试。页面没有取消请求。"
      : "请求仍在处理中，并未取消。本次结果尚未确认，你可以阅读已取得材料或已有谈话；请等请求结束后再行动或重试。");
    setError("");
    if (path === "question") setPrivateErrors((old) => ({ ...old, [errorKey]: "" }));
    let saved = false;
    let awaitingSpeech = false;
    try {
      const response = await request(path, { ...body, scriptId });
      const data = response.state || response;
      saveState(data);
      saved = true;
      awaitingSpeech = path === "scene-action" && data.sceneCue?.kind === "speech";
      if (path === "start" || path === "start-killer") setScreen("game");
      if (path === "reset") {
        setScreen("lobby");
        setInitiativeError("");
        setPrivateErrors((old) => Object.fromEntries(Object.entries(old).filter(([key]) => !key.startsWith(`${scriptId}:`))));
      }
      if (!awaitingSpeech) onSuccess?.(data);
      if (path === "question") {
        onReply(`${scriptId}:private-${body.npcId}-${data.privateChats[body.npcId].length - 1}`, response.reply,
          { ...data.roles.find((role) => role.id === body.npcId), scriptId });
      }
      if (path === "invitation-response" && body.decision === "accept" && response.reply) {
        const invitation = state.privateInvitations.find((item) => item.id === body.invitationId);
        onReply(`${scriptId}:private-${invitation.npcId}-${data.privateChats[invitation.npcId].length - 1}`, response.reply,
          { ...data.roles.find((role) => role.id === invitation.npcId), scriptId });
      }
      const completed = await completeTurns(data);
      if (awaitingSpeech) onSuccess?.(completed);
    } catch (err) {
      if (path === "question") setPrivateErrors((old) => ({ ...old, [errorKey]: err.message }));
      else setError(saved && state.case.gameType === "dungeon"
        ? `${awaitingSpeech ? "这句话的回复尚未完成，输入已保留；本次人物效果未提交。" : "现场结果已保存，人物回应尚未完成；不要重做原行动。"} ${err.message}`
        : err.message);
      try { saveState(await getState(scriptId)); } catch { /* Keep last known state. */ }
    } finally { endBusy(); }
  }

  async function resumeTurns() {
    if (busyRef.current || !state) return;
    const scriptId = state.case.id;
    busyRef.current = true;
    setError("");
    try { await completeTurns(state); }
    catch (err) {
      setError(state.case.gameType === "dungeon"
        ? `人物回复仍未完成；已保存的现场结果不会重做。 ${err.message}` : err.message);
      try { saveState(await getState(scriptId)); } catch { /* Keep last known state. */ }
    } finally { endBusy(); }
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
    beginBusy(`${state.initiativeQueue?.length || 0}位角色正在同时考虑是否找你私聊…`);
    setInitiativeError("");
    try {
      const response = await request("initiative", { scriptId });
      saveState(response.state);
      setInitiativeError((response.errors || []).map((item) => `${item.npcName}：${item.message}`).join("；"));
    } catch (err) {
      setInitiativeError(err.message);
      try { saveState(await getState(scriptId)); } catch { /* Keep last known state. */ }
    } finally { endBusy(); }
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

  return { state, scripts, screen, busy, busyHint, error, privateErrors, action,
    selectScript, openLibrary, resumeTurns, initiativeError, assessInitiative };
}
