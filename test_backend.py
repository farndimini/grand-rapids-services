"""Unit tests for projects/الوكيل/backend.py — Al-Wakeel AI backend handler."""

import http.client
import io
import json
import os
import sys
import threading
import unittest
from http.server import HTTPServer
from unittest.mock import patch, MagicMock

# Ensure the project directory is importable
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(REPO_ROOT, "projects", "\u0627\u0644\u0648\u0643\u064a\u0644")
sys.path.insert(0, BACKEND_DIR)

import backend  # noqa: E402


class TestAvailableModels(unittest.TestCase):
    """Verify the AVAILABLE_MODELS registry."""

    def test_default_model_exists(self):
        self.assertIn("gpt-4o-mini", backend.AVAILABLE_MODELS)

    def test_each_model_has_required_keys(self):
        for model_id, info in backend.AVAILABLE_MODELS.items():
            for key in ("name", "provider", "speed", "strength"):
                self.assertIn(key, info, f"Model {model_id!r} missing key {key!r}")

    def test_model_count(self):
        self.assertGreaterEqual(len(backend.AVAILABLE_MODELS), 3)


# ---------------------------------------------------------------------------
# Integration tests — spin up the real server and make HTTP requests
# ---------------------------------------------------------------------------

class TestAlWakeelServer(unittest.TestCase):
    """HTTP-level tests for the Al-Wakeel backend."""

    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), backend.AlWakeelHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _request(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(data))
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        resp_body = resp.read()
        conn.close()
        return resp, resp_body

    # ---- GET /api/models ----

    def test_get_models_returns_json(self):
        resp, body = self._request("GET", "/api/models")
        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        self.assertIn("models", data)
        self.assertIn("default", data)
        self.assertEqual(data["default"], "gpt-4o-mini")

    def test_get_models_cors_header(self):
        resp, _ = self._request("GET", "/api/models")
        self.assertEqual(resp.getheader("Access-Control-Allow-Origin"), "*")

    # ---- GET /api/unknown ----

    def test_get_unknown_api_returns_404(self):
        resp, body = self._request("GET", "/api/nonexistent")
        self.assertEqual(resp.status, 404)
        data = json.loads(body)
        self.assertIn("error", data)

    # ---- OPTIONS (CORS preflight) ----

    def test_options_returns_204(self):
        resp, _ = self._request("OPTIONS", "/api/chat")
        self.assertEqual(resp.status, 204)
        self.assertEqual(resp.getheader("Access-Control-Allow-Origin"), "*")
        self.assertIn("POST", resp.getheader("Access-Control-Allow-Methods"))

    # ---- POST /api/chat — invalid body ----

    def test_post_chat_invalid_json(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/api/chat", body=b"not-json",
                     headers={"Content-Type": "application/json", "Content-Length": "8"})
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        self.assertEqual(resp.status, 400)
        data = json.loads(body)
        self.assertIn("error", data)

    # ---- POST /api/unknown ----

    def test_post_unknown_returns_404(self):
        resp, body = self._request("POST", "/api/unknown", body={"test": True})
        self.assertEqual(resp.status, 404)

    # ---- GET static file (fallback to index.html) ----

    def test_get_root_serves_file(self):
        resp, body = self._request("GET", "/")
        # Should serve index.html or a file — 200 means it found something
        self.assertEqual(resp.status, 200)
        self.assertIn("Access-Control-Allow-Origin", dict(resp.getheaders()))

    # ---- POST /api/chat with mocked API ----

    def test_chat_with_mocked_api(self):
        """Mock the external Blues Minds API to test chat logic end-to-end."""
        fake_response = {
            "id": "test-123",
            "choices": [{"message": {"role": "assistant", "content": "Hello!"}}],
            "model": "gpt-4o-mini",
        }
        fake_bytes = json.dumps(fake_response).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_bytes
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("backend.urllib.request.urlopen", return_value=mock_resp):
            resp, body = self._request("POST", "/api/chat", body={
                "messages": [{"role": "user", "content": "How do I save money?"}],
                "model": "gpt-4o-mini",
            })

        self.assertEqual(resp.status, 200)
        data = json.loads(body)
        self.assertIn("choices", data)
        self.assertEqual(data["choices"][0]["message"]["content"], "Hello!")

    def test_chat_system_prompt_injection(self):
        """When add_system_prompt is True (default), system prompt should be prepended."""
        captured_payloads = []

        def capture_urlopen(req, **kwargs):
            payload = json.loads(req.data.decode("utf-8"))
            captured_payloads.append(payload)
            fake = json.dumps({"choices": [{"message": {"role": "assistant", "content": "ok"}}]}).encode()
            mock_resp = MagicMock()
            mock_resp.read.return_value = fake
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        with patch("backend.urllib.request.urlopen", side_effect=capture_urlopen):
            self._request("POST", "/api/chat", body={
                "messages": [{"role": "user", "content": "test"}],
            })

        self.assertEqual(len(captured_payloads), 1)
        msgs = captured_payloads[0]["messages"]
        self.assertEqual(msgs[0]["role"], "system")
        self.assertIn("Al-Wakeel", msgs[0]["content"])
        self.assertEqual(msgs[1]["role"], "user")

    def test_chat_no_system_prompt(self):
        """When add_system_prompt is False, no system prompt is prepended."""
        captured_payloads = []

        def capture_urlopen(req, **kwargs):
            payload = json.loads(req.data.decode("utf-8"))
            captured_payloads.append(payload)
            fake = json.dumps({"choices": [{"message": {"role": "assistant", "content": "ok"}}]}).encode()
            mock_resp = MagicMock()
            mock_resp.read.return_value = fake
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        with patch("backend.urllib.request.urlopen", side_effect=capture_urlopen):
            self._request("POST", "/api/chat", body={
                "messages": [{"role": "user", "content": "test"}],
                "add_system_prompt": False,
            })

        msgs = captured_payloads[0]["messages"]
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["role"], "user")

    def test_chat_custom_temperature_and_tokens(self):
        """Verify temperature and max_tokens are forwarded to the API."""
        captured = []

        def capture_urlopen(req, **kwargs):
            captured.append(json.loads(req.data.decode("utf-8")))
            fake = json.dumps({"choices": [{"message": {"role": "assistant", "content": "ok"}}]}).encode()
            mock_resp = MagicMock()
            mock_resp.read.return_value = fake
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        with patch("backend.urllib.request.urlopen", side_effect=capture_urlopen):
            self._request("POST", "/api/chat", body={
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": 0.2,
                "max_tokens": 512,
            })

        self.assertAlmostEqual(captured[0]["temperature"], 0.2)
        self.assertEqual(captured[0]["max_tokens"], 512)

    def test_chat_api_http_error(self):
        """Simulate an HTTP 429 from the upstream API."""
        import urllib.error
        err = urllib.error.HTTPError(
            url="https://api.bluesminds.com/v1/chat/completions",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=io.BytesIO(json.dumps({"message": "rate limited"}).encode()),
        )
        with patch("backend.urllib.request.urlopen", side_effect=err):
            resp, body = self._request("POST", "/api/chat", body={
                "messages": [{"role": "user", "content": "hi"}],
            })
        self.assertEqual(resp.status, 429)
        data = json.loads(body)
        self.assertIn("error", data)

    def test_chat_api_url_error(self):
        """Simulate a network connection failure."""
        import urllib.error
        err = urllib.error.URLError("Connection refused")
        with patch("backend.urllib.request.urlopen", side_effect=err):
            resp, body = self._request("POST", "/api/chat", body={
                "messages": [{"role": "user", "content": "hi"}],
            })
        self.assertEqual(resp.status, 502)

    def test_chat_api_generic_error(self):
        """Simulate an unexpected exception."""
        with patch("backend.urllib.request.urlopen", side_effect=RuntimeError("boom")):
            resp, body = self._request("POST", "/api/chat", body={
                "messages": [{"role": "user", "content": "hi"}],
            })
        self.assertEqual(resp.status, 500)


if __name__ == "__main__":
    unittest.main()
