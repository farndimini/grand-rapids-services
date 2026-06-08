#!/usr/bin/env python3
"""
الوكيل | Al-Wakeel — AI Backend Server
Proxies chat requests to Blues Minds API and serves static files.
"""

import json
import os
import urllib.request
import urllib.error
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

BLUES_MINDS_API = "https://api.bluesminds.com/v1/chat/completions"
API_KEY = "sk-98sclqUBITjMyC5a8rjgRs6Hv9IObtLqn080K7lCa80OTVwX"

# Best working models (tested)
AVAILABLE_MODELS = {
    "gpt-4o-mini": {"name": "GPT-4o Mini", "provider": "OpenAI", "speed": "fast", "strength": "high"},
    "multi-model": {"name": "Multi-Model", "provider": "Auto", "speed": "fast", "strength": "medium"},
    "qwen/qwen3.5-397b-a17b": {"name": "Qwen 3.5 397B", "provider": "Alibaba", "speed": "medium", "strength": "very high"},
    "moonshotai/kimi-k2.6": {"name": "Kimi K2.6", "provider": "Moonshot", "speed": "medium", "strength": "very high"},
    "race:moonshotai/kimi-k2.5|qwen/qwen3.5-397b-a17b": {"name": "RACE (Kimi+Qwen)", "provider": "Auto", "speed": "medium", "strength": "maximum"},
}

PROJECT_DIR = Path(__file__).parent


class AlWakeelHandler(BaseHTTPRequestHandler):

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _serve_file(self, path):
        full_path = PROJECT_DIR / path
        if not full_path.exists() or full_path.is_dir():
            full_path = PROJECT_DIR / "index.html"
        content_type, _ = mimetypes.guess_type(str(full_path))
        if content_type is None:
            content_type = "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        with open(full_path, "rb") as f:
            self.wfile.write(f.read())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/models":
            self._send_json({"models": AVAILABLE_MODELS, "default": "gpt-4o-mini"})
        elif self.path.startswith("/api/"):
            self._send_json({"error": "Not found"}, 404)
        else:
            self._serve_file(self.path.lstrip("/") or "index.html")

    def do_POST(self):
        if self.path == "/api/chat":
            self._handle_chat()
        else:
            self._send_json({"error": "Not found"}, 404)

    def _handle_chat(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._send_json({"error": "Invalid request body"}, 400)
            return

        messages = body.get("messages", [])
        model = body.get("model", "gpt-4o-mini")
        temperature = body.get("temperature", 0.7)
        max_tokens = body.get("max_tokens", 1024)
        add_system = body.get("add_system_prompt", True)

        if add_system:
            messages = [
                {"role": "system", "content": (
                    "You are الوكيل (Al-Wakeel), a friendly and expert personal finance assistant. "
                    "You help users with budgeting, saving money, getting out of debt, investing, "
                    "and building wealth. Always give practical, actionable advice. "
                    "Keep responses concise and clear. Use simple English. "
                    "If asked about something outside personal finance, politely redirect."
                )}
            ] + messages

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                BLUES_MINDS_API,
                data=data,
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                self._send_json(result)
        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read().decode("utf-8-sig"))
            except Exception:
                err_body = {"message": str(e)}
            self._send_json({"error": err_body, "status": e.code}, e.code)
        except urllib.error.URLError as e:
            self._send_json({"error": {"message": f"Connection failed: {str(e)[:100]}"}}, 502)
        except Exception as e:
            self._send_json({"error": {"message": str(e)[:200]}}, 500)


def main():
    port = int(os.environ.get("PORT", 3001))
    server = HTTPServer(("0.0.0.0", port), AlWakeelHandler)
    print(f"\n  ✨ الوكيل | Al-Wakeel AI Server")
    print(f"  ─────────────────────────────")
    print(f"  📍  http://localhost:{port}")
    print(f"  💬  Chat API: http://localhost:{port}/api/chat")
    print(f"  🤖  Models:   http://localhost:{port}/api/models")
    print(f"\n  🔥 Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  👋 Server stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
