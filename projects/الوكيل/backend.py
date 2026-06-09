#!/usr/bin/env python3
"""
الوكيل | Al-Wakeel — AI Backend Server
Proxies chat requests to Blues Minds API and serves static files.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
import mimetypes
from collections import defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

BLUES_MINDS_API = "https://api.bluesminds.com/v1/chat/completions"
API_KEY = os.environ.get("BLUES_MINDS_API_KEY", "")

if not API_KEY:
    print("WARNING: BLUES_MINDS_API_KEY not set. /api/chat will be disabled.", file=sys.stderr)

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3001").split(",")
    if o.strip()
]

MAX_TOKENS_LIMIT = 4096
MAX_MESSAGES = 50
MAX_MESSAGE_LENGTH = 8000
RATELIMIT_WINDOW = 60
RATELIMIT_MAX_REQUESTS = 30

_rate_buckets: dict[str, list[float]] = defaultdict(list)

# Best working models (tested)
AVAILABLE_MODELS = {
    "gpt-4o-mini": {"name": "GPT-4o Mini", "provider": "OpenAI", "speed": "fast", "strength": "high"},
    "multi-model": {"name": "Multi-Model", "provider": "Auto", "speed": "fast", "strength": "medium"},
    "qwen/qwen3.5-397b-a17b": {"name": "Qwen 3.5 397B", "provider": "Alibaba", "speed": "medium", "strength": "very high"},
    "moonshotai/kimi-k2.6": {"name": "Kimi K2.6", "provider": "Moonshot", "speed": "medium", "strength": "very high"},
    "race:moonshotai/kimi-k2.5|qwen/qwen3.5-397b-a17b": {"name": "RACE (Kimi+Qwen)", "provider": "Auto", "speed": "medium", "strength": "maximum"},
}

PROJECT_DIR = Path(__file__).resolve().parent


def _get_allowed_origin(request_origin: str) -> str:
    """Return the origin if it is in the allow-list, else empty string."""
    if request_origin in ALLOWED_ORIGINS:
        return request_origin
    return ""


def _is_rate_limited(client_ip: str) -> bool:
    now = time.time()
    bucket = _rate_buckets[client_ip]
    bucket[:] = [t for t in bucket if now - t < RATELIMIT_WINDOW]
    if len(bucket) >= RATELIMIT_MAX_REQUESTS:
        return True
    bucket.append(now)
    return False


class AlWakeelHandler(BaseHTTPRequestHandler):

    def _cors_headers(self):
        origin = self.headers.get("Origin", "")
        allowed = _get_allowed_origin(origin)
        if allowed:
            self.send_header("Access-Control-Allow-Origin", allowed)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _serve_file(self, path):
        full_path = (PROJECT_DIR / path).resolve()
        if not full_path.is_relative_to(PROJECT_DIR):
            self.send_error(403, "Forbidden")
            return
        if not full_path.exists() or full_path.is_dir():
            full_path = PROJECT_DIR / "index.html"
        content_type, _ = mimetypes.guess_type(str(full_path))
        if content_type is None:
            content_type = "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self._cors_headers()
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        with open(full_path, "rb") as f:
            self.wfile.write(f.read())

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
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
        if not API_KEY:
            self._send_json({"error": "Chat API is not configured"}, 503)
            return

        client_ip = self.client_address[0]
        if _is_rate_limited(client_ip):
            self._send_json({"error": "Rate limit exceeded. Try again later."}, 429)
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 100_000:
                self._send_json({"error": "Request body too large"}, 413)
                return
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._send_json({"error": "Invalid request body"}, 400)
            return

        messages = body.get("messages", [])
        if not isinstance(messages, list) or len(messages) == 0:
            self._send_json({"error": "messages must be a non-empty list"}, 400)
            return
        if len(messages) > MAX_MESSAGES:
            self._send_json({"error": f"Too many messages (max {MAX_MESSAGES})"}, 400)
            return
        for msg in messages:
            if not isinstance(msg, dict):
                self._send_json({"error": "Each message must be an object"}, 400)
                return
            content = msg.get("content", "")
            if isinstance(content, str) and len(content) > MAX_MESSAGE_LENGTH:
                self._send_json({"error": f"Message too long (max {MAX_MESSAGE_LENGTH} chars)"}, 400)
                return

        model = body.get("model", "gpt-4o-mini")
        if model not in AVAILABLE_MODELS:
            self._send_json({"error": f"Unknown model. Choose from: {', '.join(AVAILABLE_MODELS)}"}, 400)
            return

        temperature = body.get("temperature", 0.7)
        if not isinstance(temperature, (int, float)) or not (0 <= temperature <= 2):
            temperature = 0.7

        max_tokens = body.get("max_tokens", 1024)
        if not isinstance(max_tokens, int) or max_tokens < 1:
            max_tokens = 1024
        max_tokens = min(max_tokens, MAX_TOKENS_LIMIT)

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
            self._send_json({"error": {"message": "Upstream API error"}, "status": e.code}, e.code)
        except urllib.error.URLError:
            self._send_json({"error": {"message": "Upstream connection failed"}}, 502)
        except Exception:
            self._send_json({"error": {"message": "Internal server error"}}, 500)


def main():
    port = int(os.environ.get("PORT", 3001))
    bind_addr = os.environ.get("BIND_ADDRESS", "127.0.0.1")
    server = HTTPServer((bind_addr, port), AlWakeelHandler)
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
