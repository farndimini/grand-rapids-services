"""
╔══════════════════════════════════════════════════════════════╗
║              SEO AGENT PRO — API Configuration               ║
║                                                              ║
║  Set API keys via environment variables (see .env.example). ║
║  Hardcoded fallback keys are DEPRECATED and will be removed. ║
╚══════════════════════════════════════════════════════════════╝
"""

from pathlib import Path

from dotenv import load_dotenv

# Auto-load .env file if present (next to this config file)
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path, override=True)

import os

# ──────────────────────────────────────────────────────────────
#  API KEYS  —  ONLY from environment variables
#  Set them in .env (see .env.example)
# ──────────────────────────────────────────────────────────────

API_KEYS = {
    "anthropic":  os.environ.get("ANTHROPIC_API_KEY",     ""),
    "openrouter": os.environ.get("OPENROUTER_API_KEY",    ""),
    "groq":       os.environ.get("GROQ_API_KEY",          ""),
    "google":     os.environ.get("GOOGLE_API_KEY",        ""),
    "deepseek":   os.environ.get("DEEPSEEK_API_KEY",      ""),
    "cloudflare": os.environ.get("CLOUDFLARE_API_TOKEN",  ""),
    "bluesminds": os.environ.get("BLUESMINDS_API_KEY",    ""),
    "local":      "",
}

# ──────────────────────────────────────────────────────────────
#  AVAILABLE MODELS
#  Format: "display_name": ("provider", "model_id")
# ──────────────────────────────────────────────────────────────

MODELS = {
    # ── Anthropic ──────────────────────────────────────────────
    "claude-sonnet-4":      ("anthropic",   "claude-sonnet-4-20250514"),
    "claude-haiku":         ("anthropic",   "claude-haiku-4-5-20251001"),

    # ── OpenRouter ─────────────────────────────────────────────
    "gpt-4o":               ("openrouter",  "openai/gpt-4o"),
    "gpt-4o-mini":          ("openrouter",  "openai/gpt-4o-mini"),
    "gemini-pro":           ("openrouter",  "google/gemini-pro-1.5"),
    "gemini-flash":         ("openrouter",  "google/gemini-flash-1.5"),
    "mistral-large":        ("openrouter",  "mistralai/mistral-large"),
    "llama-3.3-70b":        ("openrouter",  "meta-llama/llama-3.3-70b-instruct"),
    "deepseek-r1":          ("openrouter",  "deepseek/deepseek-r1"),
    "qwen-2.5-72b":         ("openrouter",  "qwen/qwen-2.5-72b-instruct"),

    # ── Google Gemini (free tier via AI Studio) ────────────────
    "gemini-2.0-flash":     ("google",      "gemini-2.0-flash"),
    "gemini-2.0-flash-lite":("google",      "gemini-2.0-flash-lite"),
    "gemini-1.5-pro":       ("google",      "gemini-1.5-pro"),
    "gemini-1.5-flash":     ("google",      "gemini-1.5-flash"),

    # ── Groq (ultra-fast) ──────────────────────────────────────
    "llama-3.3-70b-groq":   ("groq",        "llama-3.3-70b-versatile"),
    "llama-4-scout-groq":   ("groq",        "meta-llama/llama-4-scout-17b-16e-instruct"),
    "qwen-3-32b-groq":      ("groq",        "qwen/qwen3-32b"),
    "llama-3.1-8b-groq":    ("groq",        "llama-3.1-8b-instant"),

    # ── DeepSeek (direct API) ──────────────────────────────────
    "deepseek-chat":        ("deepseek",    "deepseek-chat"),
    "deepseek-reasoner":    ("deepseek",    "deepseek-reasoner"),

    # ── Cloudflare Workers AI ───────────────────────────────────
    "cf-llama-3.3-70b":     ("cloudflare",  "@cf/meta/llama-3.3-70b-instruct-fp8-fast"),
    "cf-llama-3.1-8b":      ("cloudflare",  "@cf/meta/llama-3.1-8b-instruct"),
    "cf-llama-3.2-3b":      ("cloudflare",  "@cf/meta/llama-3.2-3b-instruct"),
    "cf-mistral-7b":        ("cloudflare",  "@cf/mistral/mistral-7b-instruct-v0.1"),
    "cf-deepseek-r1-32b":   ("cloudflare",  "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b"),

    # ── BluesMinds (OpenAI-compatible, custom endpoint) ──────────
    "bluesminds-gemini-3.1-pro":    ("bluesminds",  "gemini-3.1-pro"),
    "bluesminds-gemini-3.5-flash":  ("bluesminds",  "gemini-3.5-flash"),
    "bluesminds-gpt-4o-mini":       ("bluesminds",  "gpt-4o-mini"),
    "bluesminds-gpt-4o":            ("bluesminds",  "gpt-4o"),

    # ── Local (AI Assistant, no API key needed) ─────────────────
    "local":                ("local",       "local-llm"),
}

# ──────────────────────────────────────────────────────────────
#  DEFAULT MODEL
#  Change this to set which model runs by default
# ──────────────────────────────────────────────────────────────

DEFAULT_MODEL = "bluesminds-gemini-3.5-flash"

# ──────────────────────────────────────────────────────────────
#  GENERATION SETTINGS
# ──────────────────────────────────────────────────────────────

SETTINGS = {
    "max_tokens":    4096,
    "temperature":   0.7,
    "stream":        True,
    "output_dir":    "output",
    "memory_file":   "seo_memory.json",
    "site_url":      os.environ.get("SITE_URL", "https://yoursite.com"),
    "site_name":     os.environ.get("SITE_NAME", "James Whitfield"),
    "author_name":   os.environ.get("AUTHOR_NAME", "James Whitfield"),
    "cloudflare_account_id": os.environ.get("CLOUDFLARE_ACCOUNT_ID", ""),
    "bluesminds_api_base": os.environ.get("BLUESMINDS_API_BASE", "https://api.bluesminds.com/v1"),
}

# ──────────────────────────────────────────────────────────────
#  GOOGLE SEARCH CONSOLE (required for production)
#  Set GSC_SITE_URL + GSC_CREDENTIALS_PATH in .env
# ──────────────────────────────────────────────────────────────

GSC_CONFIG = {
    "site_url":           os.environ.get("GSC_SITE_URL", ""),
    "credentials_path":   os.environ.get("GSC_CREDENTIALS_PATH", ""),
}

# ──────────────────────────────────────────────────────────────
#  CELERY / REDIS — Distributed task queue configuration
#  Set these in .env to enable distributed execution.
#  The system falls back to in-process execution if Redis is down.
# ──────────────────────────────────────────────────────────────

CELERY_CONFIG = {
    "broker_url":          os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    "result_backend_url":  os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
    "worker_concurrency":  int(os.environ.get("CELERY_WORKER_CONCURRENCY", "4")),
    "task_timeout":        int(os.environ.get("CELERY_TASK_TIMEOUT", "300")),
    "task_soft_timeout":   int(os.environ.get("CELERY_TASK_SOFT_TIMEOUT", "270")),
    "default_queue":       os.environ.get("CELERY_DEFAULT_QUEUE", "seo_agent"),
    "result_expires_hours": int(os.environ.get("CELERY_RESULT_EXPIRES_HOURS", "1")),
}

# ──────────────────────────────────────────────────────────────
#  ASYNC RUNTIME SETTINGS
# ──────────────────────────────────────────────────────────────

ASYNC_CONFIG = {
    "max_concurrency": int(os.environ.get("ASYNC_MAX_CONCURRENCY", "10")),
    "request_timeout": float(os.environ.get("ASYNC_TIMEOUT", "90")),
    "provider_limits": {
        "anthropic": int(os.environ.get("ASYNC_LIMIT_ANTHROPIC", "3")),
        "openrouter": int(os.environ.get("ASYNC_LIMIT_OPENROUTER", "5")),
        "groq": int(os.environ.get("ASYNC_LIMIT_GROQ", "6")),
        "deepseek": int(os.environ.get("ASYNC_LIMIT_DEEPSEEK", "5")),
        "cloudflare": int(os.environ.get("ASYNC_LIMIT_CLOUDFLARE", "10")),
        "bluesminds": int(os.environ.get("ASYNC_LIMIT_BLUESMINDS", "5")),
        "google": int(os.environ.get("ASYNC_LIMIT_GOOGLE", "4")),
        "local": int(os.environ.get("ASYNC_LIMIT_LOCAL", "20")),
    },
    "enable_async": os.environ.get("ASYNC_ENABLED", "true").lower() == "true",
}
