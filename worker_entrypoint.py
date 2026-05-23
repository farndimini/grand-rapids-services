#!/usr/bin/env python3
"""
worker_entrypoint.py — Celery Worker Entrypoint for SEO Agent Pro
===================================================================
Starts a Celery worker that processes distributed SEO tasks.

Usage:
    python worker_entrypoint.py [--concurrency 4] [--loglevel info]
    python worker_entrypoint.py --help

Environment variables (from .env or config.py CELERY_CONFIG):
    CELERY_BROKER_URL      (default: redis://localhost:6379/0)
    CELERY_RESULT_BACKEND  (default: redis://localhost:6379/0)

Graceful shutdown:
    Send SIGTERM or SIGINT to drain in-flight tasks before stopping.

Integration with main.py:
    python main.py --keyword "best laptop" --model local --distributed
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("worker_entrypoint")

# Global flag for graceful shutdown
_shutdown_requested = False


def _handle_signal(signum, frame):
    global _shutdown_requested
    if _shutdown_requested:
        log.warning("Forced shutdown (double signal)")
        sys.exit(1)
    _shutdown_requested = True
    log.info(f"Received signal {signum} — draining tasks before shutdown...")


# ── Health-check endpoint (for monitoring) ─────────────────────

def _run_health_server(port: int) -> None:
    """Minimal HTTP health-check server in a daemon thread."""
    import http.server
    import json
    import threading

    class HealthHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                from agent_core.task_queue import get_task_queue
                queue = get_task_queue()
                stats = queue.stats()
                body = json.dumps({
                    "status": "healthy",
                    "uptime_hours": stats.get("uptime_hours", 0),
                    "tasks_by_state": stats.get("tasks_by_state", {}),
                    "mode": stats.get("mode", "unknown"),
                }).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                error_body = json.dumps({"status": "unhealthy", "error": str(e)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(error_body)))
                self.end_headers()
                self.wfile.write(error_body)

        def log_message(self, format, *args):
            pass  # suppress HTTP log noise

    server = http.server.HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="health_server")
    thread.start()
    log.info(f"[WORKER] Health server running on port {port}")


# ── Main ───────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="seo-agent-worker",
        description="Celery worker for SEO Agent Pro distributed tasks",
    )
    parser.add_argument("--concurrency", type=int, default=None,
                        help="Number of worker processes (default: from config or 4)")
    parser.add_argument("--loglevel", default="info",
                        choices=["debug", "info", "warning", "error"],
                        help="Logging level (default: info)")
    parser.add_argument("--queues", default=None,
                        help="Comma-separated queues to listen on (default: seo_agent)")
    parser.add_argument("--hostname", default=None,
                        help="Custom worker hostname (for telemetry)")
    parser.add_argument("--health-port", type=int, default=0,
                        help="Port for HTTP health-check endpoint (0 = disabled)")
    parser.add_argument("--no-celery", action="store_true",
                        help="Run in-process only (no Redis/Celery needed)")
    args = parser.parse_args()

    health_port = args.health_port

    if args.no_celery:
        log.info("[WORKER] Running in in-process mode (no Celery/Redis needed)")
        log.info("[WORKER] Tasks will execute synchronously in the main process")
        log.info("[WORKER] Use --distributed flag in main.py to route through task queue")

        if health_port > 0:
            _run_health_server(health_port)

        # Keep alive until signal
        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

        log.info("[WORKER] In-process worker ready. Press Ctrl+C to stop.")
        while not _shutdown_requested:
            time.sleep(1)

        log.info("[WORKER] Shutting down in-process worker...")
        _shutdown()
        return

    # ── Celery mode ──────────────────────────────────────────
    log.info("[WORKER] Starting Celery worker...")

    # Install signal handlers before starting Celery
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if health_port > 0:
        _run_health_server(health_port)

    try:
        from agent_core.worker_tasks import app as celery_app
    except ImportError as e:
        log.error(f"[WORKER] Failed to import Celery app: {e}")
        log.error("[WORKER] Install Celery: pip install celery redis")
        sys.exit(1)

    # Build argv for Celery worker
    celery_argv = [
        "worker",
        "--loglevel", args.loglevel,
    ]

    if args.concurrency:
        celery_argv.extend(["--concurrency", str(args.concurrency)])
    else:
        from config import CELERY_CONFIG
        concurrency = CELERY_CONFIG.get("worker_concurrency", 4)
        celery_argv.extend(["--concurrency", str(concurrency)])

    if args.queues:
        celery_argv.extend(["--queues", args.queues])

    if args.hostname:
        celery_argv.extend(["--hostname", args.hostname])

    log.info(f"[WORKER] Starting with args: {' '.join(celery_argv)}")
    try:
        celery_app.worker_main(celery_argv)
    except KeyboardInterrupt:
        log.info("[WORKER] KeyboardInterrupt — shutting down...")

    _shutdown()


def _shutdown() -> None:
    """Graceful shutdown of the worker and task queue."""
    try:
        from agent_core.task_queue import get_task_queue
        queue = get_task_queue()
        summary = queue.shutdown(timeout=15)
        log.info(f"[WORKER] Queue shutdown: {summary}")
    except Exception as e:
        log.warning(f"[WORKER] Queue shutdown error: {e}")
    log.info("[WORKER] Worker shutdown complete")


if __name__ == "__main__":
    main()
