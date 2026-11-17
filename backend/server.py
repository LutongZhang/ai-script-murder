from __future__ import annotations

import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

if __package__:
    from .game import Game, GameError
    from .npc_ai import AIError, generate_reply, start_ai, stop_ai, ai_status
    from .scripts import DEFAULT_SCRIPT_ID, load_scripts, script_summary
else:
    from game import Game, GameError
    from npc_ai import AIError, generate_reply, start_ai, stop_ai, ai_status
    from scripts import DEFAULT_SCRIPT_ID, load_scripts, script_summary

BASE_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = BASE_DIR / "frontend" / "dist"
SCRIPTS = load_scripts()
GAMES = {script_id: Game(script, generate_reply) for script_id, script in SCRIPTS.items()}
# Keep the original default-script entry points usable for local integrations.
CASE_DATA = SCRIPTS[DEFAULT_SCRIPT_ID]
GAME = GAMES[DEFAULT_SCRIPT_ID]


def get_game(script_id: Any = DEFAULT_SCRIPT_ID) -> Game:
    if not isinstance(script_id, str):
        raise GameError("scriptId 必须是字符串。", 400)
    if script_id not in GAMES:
        raise GameError("这个剧本不存在，请返回剧本库重新选择。", 404)
    return GAMES[script_id]


def script_catalog() -> dict[str, Any]:
    return {
        "defaultScriptId": DEFAULT_SCRIPT_ID,
        "scripts": [
            {**script_summary(script), "progress": {
                "started": bool(state["player"]), "phase": state["phase"],
                "phaseLabel": state["phaseLabel"],
                "playerName": state["player"]["name"] if state["player"] else None,
            }}
            for script_id, script in SCRIPTS.items()
            for state in [GAMES[script_id].state()]
        ],
    }


class RequestHandler(BaseHTTPRequestHandler):
    def _write_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _write_file(self, file_path: Path) -> None:
        content = file_path.read_bytes()
        content_type, _ = mimetypes.guess_type(str(file_path))
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_frontend(self, request_path: str) -> None:
        if not DIST_DIR.exists():
            self._write_json({"error": "前端尚未构建，请执行 npm --prefix frontend run build。"},
                             HTTPStatus.SERVICE_UNAVAILABLE)
            return
        relative_path = request_path.lstrip("/") or "index.html"
        candidate = (DIST_DIR / relative_path).resolve()
        if DIST_DIR.resolve() not in candidate.parents and candidate != DIST_DIR.resolve():
            self._write_json({"error": "Invalid path"}, HTTPStatus.BAD_REQUEST)
            return
        self._write_file(candidate if candidate.is_file() else DIST_DIR / "index.html")

    def do_OPTIONS(self) -> None:
        self._write_json({"ok": True})

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        try:
            if url.path == "/api/ai-status":
                self._write_json(ai_status())
            elif url.path == "/api/scripts":
                self._write_json(script_catalog())
            elif url.path == "/api/state":
                script_id = parse_qs(url.query).get("scriptId", [DEFAULT_SCRIPT_ID])[0]
                self._write_json(get_game(script_id).state())
            elif url.path.startswith("/api/"):
                self._write_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            else:
                self._serve_frontend(url.path)
        except GameError as exc:
            self._write_json({"error": str(exc)}, exc.status)

    def do_POST(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= content_length <= 65536:
                raise ValueError("Invalid content length")
            raw_body = self.rfile.read(content_length) if content_length else b"{}"
            payload = json.loads(raw_body.decode("utf-8"))
        except (ValueError, UnicodeError):
            self._write_json({"error": "请求必须是有效 JSON，且不超过 64 KB。"}, HTTPStatus.BAD_REQUEST)
            return
        if not isinstance(payload, dict):
            self._write_json({"error": "请求 JSON 必须是对象。"}, HTTPStatus.BAD_REQUEST)
            return

        def text_field(name: str, default: str | None = None) -> str:
            value = payload.get(name, default)
            if not isinstance(value, str):
                raise GameError(f"{name} 必须是字符串。", 400)
            return value

        try:
            game = get_game(payload.get("scriptId", DEFAULT_SCRIPT_ID))
            path = urlsplit(self.path).path
            if path == "/api/reset":
                response = game.reset()
            elif path == "/api/start":
                response = game.start(text_field("roleId"))
            elif path == "/api/start-killer":
                response = game.start(mode="killer")
            elif path == "/api/advance":
                response = game.advance(confirm_accusation=payload.get("confirmAccusation") is True)
            elif path == "/api/search":
                response = game.search(text_field("locationId"))
            elif path == "/api/publish":
                response = game.publish(text_field("evidenceId"))
            elif path == "/api/question":
                response = game.private(text_field("npcId"), text_field("question"))
            elif path == "/api/initiative":
                response = game.initiative()
            elif path == "/api/invitation-response":
                response = game.respond_invitation(text_field("invitationId"), text_field("decision"))
            elif path == "/api/discuss":
                response = game.discuss(text_field("message", ""))
            elif path == "/api/ai-turn":
                response = game.ai_turn()
            elif path == "/api/vote":
                response = game.vote(text_field("targetId"))
            else:
                self._write_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
                return
        except (AIError, GameError) as exc:
            self._write_json({"error": str(exc)}, exc.status)
            return
        self._write_json(response)

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    host = os.getenv("NPC_HOST", "127.0.0.1")
    port = int(os.getenv("NPC_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), RequestHandler)
    try:
        start_ai()
        print(f"AI service: {json.dumps(ai_status(), ensure_ascii=False)}")
    except AIError as exc:
        print(f"AI service unavailable: {exc}")
    print(f"Loaded {len(SCRIPTS)} scripts. App running on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        stop_ai()


if __name__ == "__main__":
    main()
