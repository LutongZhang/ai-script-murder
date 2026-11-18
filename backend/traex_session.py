from __future__ import annotations

import json
import os
import selectors
import shutil
import signal
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory, TemporaryFile
from threading import RLock
from typing import Any


class TraexSessionError(Exception):
    def __init__(self, message: str, status: int = 502) -> None:
        super().__init__(message)
        self.status = status


class TraexWorker:
    """One owned stdio connection; its lock protects generation and repair."""

    def __init__(self) -> None:
        self.lock = RLock()
        self.process: subprocess.Popen | None = None
        self.selector: selectors.BaseSelector | None = None
        self.workdir: TemporaryDirectory | None = None
        self.stderr: Any = None
        self.buffer = b""
        self.notifications: list[dict[str, Any]] = []
        self.request_id = 0
        self.sessions: dict[str, dict[str, str]] = {}
        self.configuration: tuple[str, str] | None = None
        self.game_id: str | None = None
        self.starts = 0
        self.ready = False
        self.last_error = ""
        self.last_format_error: dict[str, Any] | None = None
        self.format_retries = 0

    def status(self) -> dict[str, Any]:
        process = self.process
        running = process is not None and process.poll() is None
        return {
            "transport": "stdio", "running": running, "ready": running and self.ready,
            "pid": process.pid if running else None, "processStarts": self.starts,
            "sessionCount": len(self.sessions), "lastError": self.last_error,
            "formatRetries": self.format_retries, "lastFormatError": self.last_format_error,
        }

    def _stop(self) -> None:
        self.ready = False
        process = self.process
        self.process = None
        if process is not None:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            if process.poll() is None:
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    except PermissionError:
                        process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        except PermissionError:
                            process.kill()
                        process.wait(timeout=3)
            for stream in (process.stdin, process.stdout):
                if stream:
                    stream.close()
        if self.selector:
            self.selector.close()
        if self.stderr:
            self.stderr.close()
        if self.workdir:
            self.workdir.cleanup()
        self.selector = self.stderr = self.workdir = None
        self.buffer = b""
        self.notifications.clear()
        self.sessions.clear()
        self.game_id = None
        self.configuration = None

    def close(self) -> None:
        # EOF asks the app-server to shut down and wakes an outstanding reader.
        process = self.process
        if process and process.stdin and not process.stdin.closed:
            try:
                process.stdin.close()
            except OSError:
                pass
        with self.lock:
            self._stop()

    def invalidate(self, role_id: str, reason: str = "") -> None:
        with self.lock:
            self.last_error = reason
            if role_id in self.sessions:
                self._stop()

    def _error(self, details: str = "") -> TraexSessionError:
        if self.stderr:
            self.stderr.flush()
            self.stderr.seek(0, os.SEEK_END)
            size = self.stderr.tell()
            self.stderr.seek(max(0, size - 16384))
            details += self.stderr.read().decode("utf-8", errors="replace")
        lower = details.lower()
        if "permission denied" in lower:
            return TraexSessionError(
                "traex 常驻服务被当前运行环境拒绝启动（权限不足）。"
                "请检查后端运行环境的权限；本轮未保存。", 503)
        if "unauthorized" in lower or "not logged in" in lower:
            return TraexSessionError("traex 认证失败，请在后端所在账号执行 traex login。", 503)
        if "unknown feature flag" in lower or "unexpected argument" in lower:
            return TraexSessionError("当前 traex 版本不支持常驻服务的启动参数，请检查 CLI 版本。", 503)
        return TraexSessionError("traex 常驻服务退出或请求失败，本轮未保存。请检查 CLI 日志。")

    def _send(self, message: dict[str, Any]) -> None:
        if not self.process or not self.process.stdin:
            raise self._error()
        self.process.stdin.write(json.dumps(message, ensure_ascii=False).encode("utf-8") + b"\n")
        self.process.stdin.flush()

    def _receive(self, deadline: float) -> dict[str, Any]:
        while True:
            if b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                if not line.strip():
                    continue
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise TraexSessionError("traex 常驻协议返回无效消息，本轮未保存。")
                # No tool, permission, or interactive-input requests are accepted.
                if "method" in event and "id" in event:
                    self._send({"id": event["id"], "error": {
                        "code": -32601, "message": "This client supports dialogue only.",
                    }})
                    continue
                return event
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not self.selector or not self.selector.select(remaining):
                raise TraexSessionError("traex 回答超时，本轮未保存，请重试。", 504)
            if not self.process or not self.process.stdout:
                raise self._error()
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                raise self._error()
            self.buffer += chunk
            if len(self.buffer) > 4 * 1024 * 1024:
                raise TraexSessionError("traex 返回的协议消息过大，本轮未保存。")

    def _request(self, method: str, params: dict[str, Any], deadline: float) -> dict[str, Any]:
        self.request_id += 1
        request_id = self.request_id
        self._send({"id": request_id, "method": method, "params": params})
        while True:
            try:
                event = self._receive(deadline)
            except TraexSessionError as exc:
                if exc.status == 504:
                    raise TraexSessionError(
                        f"traex 常驻服务在 {method} 阶段超时，本轮未保存。", 504) from exc
                raise
            if event.get("id") == request_id:
                if "error" in event:
                    raise self._error(str(event["error"]))
                result = event.get("result")
                if not isinstance(result, dict):
                    raise TraexSessionError("traex 常驻协议返回无效结果，本轮未保存。")
                return result
            if event.get("method") in {"item/completed", "turn/completed"}:
                self.notifications.append(event)

    def _start(self, config: dict[str, str], deadline: float) -> None:
        configuration = (config["traex_command"], config["traex_model"])
        if self.ready and self.process and self.process.poll() is None and self.configuration == configuration:
            return
        self._stop()
        executable = shutil.which(config["traex_command"])
        if not executable:
            raise TraexSessionError("找不到 traex，请设置 NPC_AI_TRAEX_COMMAND 为 CLI 路径。", 503)
        self.workdir = TemporaryDirectory(prefix="npc-traex-session-")
        self.stderr = TemporaryFile(mode="w+b")
        command = [
            executable, "--allowed-tool", "npc_dialogue_only",
            "-c", 'approval_policy="never"', "-c", 'sandbox_mode="read-only"',
            "-c", "project_doc_max_bytes=0", "-c", "mcp_servers={}",
            "-c", "sqlite_home=" + json.dumps(self.workdir.name),
            "-c", "log_dir=" + json.dumps(self.workdir.name),
        ]
        for feature in (
            "shell_tool", "shell_snapshot", "shell_snapshot_v2", "unified_exec",
            "apply_patch_freeform", "apps", "plugins", "hooks", "memories",
            "multi_agent", "multi_agent_v2", "browser_use", "browser_use_external",
            "computer_use", "code_mode", "code_mode_host", "tool_search", "tool_suggest",
            "image_generation", "goals", "prevent_idle_sleep",
        ):
            command.extend(["--disable", feature])
        command.extend(["app-server", "--listen", "stdio://"])
        self.process = subprocess.Popen(
            command, cwd=self.workdir.name, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=self.stderr, start_new_session=True,
        )
        self.starts += 1
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        self._request("initialize", {"clientInfo": {
            "name": "npc-dialogue", "title": "雨夜封锁", "version": "1.0",
        }}, deadline)
        self._send({"method": "initialized", "params": {}})
        self.configuration = configuration
        self.ready = True
        self.last_error = ""

    def start(self, config: dict[str, str]) -> None:
        with self.lock:
            try:
                self._start(config, time.monotonic() + 20)
            except (TraexSessionError, OSError, ValueError) as exc:
                error = exc if isinstance(exc, TraexSessionError) else self._error()
                self.last_error = str(error)
                self._stop()
                raise error from exc

    def reply(self, config: dict[str, str], system_prompt: str, context: dict[str, Any],
              history: list[dict[str, str]], question: str,
              format_correction: str | None = None) -> tuple[str, str]:
        try:
            timeout = float(config["traex_timeout"])
            if not 0 < timeout <= 600:
                raise ValueError()
        except ValueError as exc:
            raise TraexSessionError("NPC_AI_TIMEOUT 必须是 0 到 600 之间的秒数。", 503) from exc
        role_id = context["yourCharacter"]["id"]
        game_id = context["sessionId"]
        with self.lock:
            deadline = time.monotonic() + timeout
            try:
                if self.game_id is not None and self.game_id != game_id:
                    self._stop()
                self._start(config, deadline)
                self.game_id = game_id
                schema = json.loads(Path(__file__).with_name("npc_response.schema.json").read_text())
                if context.get("mode") == "intent":
                    schema = {"type": "object", "additionalProperties": False,
                              "properties": {
                                  "intentId": {"type": "string", "enum": [a["id"] for a in context["availableIntents"]]},
                                  "reply": {"type": "string"}},
                              "required": ["intentId", "reply"]}
                if context.get("mode") == "dungeon":
                    schema["properties"]["npcActionId"] = {
                        "type": "string", "enum": [a["id"] for a in context["availableNpcActions"]]}
                    schema["required"].append("npcActionId")
                session = self.sessions.get(role_id)
                # A thread may include a response that the game rejected after generation.
                # Reuse it only when its last turn was actually committed by the game.
                if session and session["lastResponseId"] != context.get("lastResponseId"):
                    self.sessions.pop(role_id)
                    session = None
                if not session:
                    result = self._request("thread/start", {
                        "model": config["traex_model"], "cwd": self.workdir.name,
                        "sandbox": "read-only", "approvalPolicy": "never", "ephemeral": True,
                        "baseInstructions": system_prompt,
                        "developerInstructions": (
                            "这是纯角色对话任务，不读取文件、不执行命令、不调用工具。"
                            "最终回答必须只包含一个符合以下Schema的JSON对象，不加说明或Markdown。"
                            "字段名和字符串必须使用双引号，字符串中的双引号、换行等必须正确转义。"
                            "所有角色发言只放在reply字段，所有必需字段都要提供。Schema："
                            + json.dumps(schema, ensure_ascii=False)
                        ),
                    }, deadline)
                    session = {"threadId": result["thread"]["id"], "lastResponseId": ""}
                    self.sessions[role_id] = session
                    payload = {"context": context, "confirmedPrivateHistory": history[-20:],
                               "question": question}
                else:
                    # The app-server thread already contains previous turns.
                    payload = {"context": context, "question": question}
                if format_correction:
                    payload["formatCorrection"] = {
                        "previousOutputAccepted": False,
                        "error": format_correction,
                        "instruction": (
                            "上一轮输出未通过校验，未向玩家展示或保存。请重新生成本轮question的完整回答，"
                            "只输出符合Schema的JSON对象。格式说明不是游戏内的新发言。"
                            "遵守context中的事实、已保存记忆及线索归属，不编造事实；"
                            "evidenceIds只能选context允许的线索，voteId按mode和voteOptions填写。"
                        ),
                    }
                result = self._request("turn/start", {
                    "threadId": session["threadId"],
                    "input": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
                    "outputSchema": schema,
                }, deadline)
                turn_id = result["turn"]["id"]
                messages: dict[str, dict[str, Any]] = {}
                while True:
                    event = self.notifications.pop(0) if self.notifications else self._receive(deadline)
                    params = event.get("params", {})
                    if params.get("threadId") != session["threadId"]:
                        continue
                    if event.get("method") == "item/completed" and params.get("turnId") == turn_id:
                        item = params["item"]
                        if item.get("type") == "agentMessage" and item.get("phase") in {None, "final_answer"}:
                            messages[item["id"]] = item
                    elif event.get("method") == "turn/completed" and params["turn"]["id"] == turn_id:
                        turn = params["turn"]
                        if turn["status"] != "completed":
                            raise self._error(str(turn.get("error", "")))
                        for item in turn.get("items", []):
                            if item.get("type") == "agentMessage" and item.get("phase") in {None, "final_answer"}:
                                messages[item["id"]] = item
                        if not messages:
                            raise TraexSessionError("traex 本轮没有返回角色发言，本轮未保存。")
                        response_id = session["threadId"] + "/" + turn_id
                        session["lastResponseId"] = response_id
                        self.last_error = ""
                        finals = [item for item in messages.values() if item.get("phase") == "final_answer"]
                        return (finals or list(messages.values()))[-1]["text"], response_id
            except (TraexSessionError, OSError, ValueError, KeyError, TypeError) as exc:
                error = exc if isinstance(exc, TraexSessionError) else self._error()
                self.last_error = str(error)
                # Discard this role's CLI state without interrupting other roles.
                self._stop()
                raise error from exc


class TraexSession:
    """Independent connections per story and role, allowing concurrent turns."""

    def __init__(self) -> None:
        self.lock = RLock()
        self.workers: dict[tuple[str, str], TraexWorker] = {}
        self.warm: TraexWorker | None = None

    def start(self, config: dict[str, str]) -> None:
        with self.lock:
            if self.warm is None and not self.workers:
                self.warm = TraexWorker()
            worker = self.warm
        if worker:
            worker.start(config)

    def for_character(self, context: dict[str, Any]) -> TraexWorker:
        key = (context["scriptId"], context["yourCharacter"]["id"])
        with self.lock:
            if key not in self.workers:
                self.workers[key] = self.warm or TraexWorker()
                self.warm = None
            return self.workers[key]

    def status(self) -> dict[str, Any]:
        with self.lock:
            workers = list(self.workers.values()) + ([self.warm] if self.warm else [])
        statuses = [worker.status() for worker in workers]
        running = [item for item in statuses if item["running"]]
        return {
            "transport": "stdio", "running": bool(running),
            "ready": any(item["ready"] for item in statuses),
            "pid": running[0]["pid"] if running else None,
            "pids": [item["pid"] for item in running],
            "processStarts": sum(item["processStarts"] for item in statuses),
            "sessionCount": sum(item["sessionCount"] for item in statuses),
            "lastError": next((item["lastError"] for item in statuses if item["lastError"]), ""),
            "formatRetries": sum(item["formatRetries"] for item in statuses),
            "lastFormatError": next((item["lastFormatError"] for item in statuses
                                     if item["lastFormatError"]), None),
        }

    def close(self) -> None:
        with self.lock:
            workers = list(self.workers.values()) + ([self.warm] if self.warm else [])
        for worker in workers:
            worker.close()
