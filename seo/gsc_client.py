"""
GSC Client — production-only Google Search Console connector.
Raises on missing credentials. No simulation. No random.
"""
from __future__ import annotations
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("gsc")

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "gsc"


class GSCClient:
    """One GSC service account, authenticated on init."""

    def __init__(self, site_url: str = "", credentials_path: str = ""):
        self.site_url = site_url or os.getenv("GSC_SITE_URL", "")
        self.credentials_path = (
            credentials_path
            or os.getenv("GSC_CREDENTIALS_PATH", "")
            or os.getenv("GSC_CREDENTIALS", "")
        )

        if not self.site_url or not self.credentials_path:
            raise RuntimeError(
                "GSC not configured. Set GSC_SITE_URL and GSC_CREDENTIALS_PATH "
                "in .env or pass them to GSCClient()."
            )
        if not Path(self.credentials_path).exists():
            raise FileNotFoundError(
                f"GSC credentials file not found: {self.credentials_path}"
            )

        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            self.credentials_path,
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
        )
        self.service = build("searchconsole", "v1", credentials=creds)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Verify access
        try:
            self.service.sites().get(siteUrl=self.site_url).execute()
        except Exception as e:
            log.warning(f"GSC site access check failed: {e}")

    # ── Cache helpers ────────────────────────────────────────

    def _cache_key(self, keyword: str) -> Path:
        h = hashlib.md5(keyword.lower().strip().encode()).hexdigest()
        return CACHE_DIR / f"{h}.json"

    def _cache_read(self, keyword: str) -> dict | None:
        path = self._cache_key(keyword)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            cached_at = datetime.fromisoformat(data.get("_cached_at", "2000-01-01"))
            if datetime.now() - cached_at < timedelta(hours=1):
                return data
        except Exception:
            log.debug("[GSC] Cache read failed for '%s'", keyword)
        return None

    def _cache_write(self, keyword: str, data: dict) -> None:
        data["_cached_at"] = datetime.now().isoformat()
        data["_keyword"] = keyword
        self._cache_key(keyword).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ── Core GSC queries ─────────────────────────────────────

    def get_keyword_data(self, keyword: str, days: int = 28) -> dict:
        """Fetch real GSC data for one keyword. Returns raw API row or empty dict."""
        cached = self._cache_read(keyword)
        if cached and cached.get("source") == "gsc_api":
            return cached

        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        end = datetime.now().strftime("%Y-%m-%d")

        body = {
            "startDate": start,
            "endDate": end,
            "dimensions": ["query"],
            "dimensionFilterGroups": [{
                "filters": [{"dimension": "query", "expression": keyword}]
            }],
            "rowLimit": 1,
        }
        response = self.service.searchanalytics().query(
            siteUrl=self.site_url, body=body
        ).execute()
        rows = response.get("rows", [])

        data = {
            "keyword": keyword,
            "source": "gsc_api",
            "fetched_at": datetime.now().isoformat(),
        }
        if rows:
            row = rows[0]
            data.update({
                "position": round(row.get("position", 0), 1),
                "ctr": round(row.get("ctr", 0) * 100, 2),
                "impressions": row.get("impressions", 0),
                "clicks": row.get("clicks", 0),
            })
        else:
            data.update({"position": None, "ctr": 0, "impressions": 0, "clicks": 0})

        self._cache_write(keyword, data)
        return data

    def get_top_queries(self, days: int = 28, max_results: int = 100) -> list[dict]:
        """Top queries from GSC by impression volume."""
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        end = datetime.now().strftime("%Y-%m-%d")

        body = {
            "startDate": start,
            "endDate": end,
            "dimensions": ["query"],
            "rowLimit": max_results,
        }
        response = self.service.searchanalytics().query(
            siteUrl=self.site_url, body=body
        ).execute()

        return [{
            "query": row.get("keys", [""])[0],
            "position": round(row.get("position", 0), 1),
            "impressions": row.get("impressions", 0),
            "clicks": row.get("clicks", 0),
            "ctr": round(row.get("ctr", 0) * 100, 2),
        } for row in response.get("rows", [])]

    def get_ranking_history(
        self, keyword: str, days: int = 28
    ) -> list[dict]:
        """Daily position history from GSC for one keyword."""
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        end = datetime.now().strftime("%Y-%m-%d")

        body = {
            "startDate": start,
            "endDate": end,
            "dimensions": ["query", "date"],
            "dimensionFilterGroups": [{
                "filters": [{"dimension": "query", "expression": keyword}]
            }],
            "rowLimit": days,
        }
        response = self.service.searchanalytics().query(
            siteUrl=self.site_url, body=body
        ).execute()

        return [{
            "date": row.get("keys", ["", ""])[1],
            "position": round(row.get("position", 0), 1),
        } for row in response.get("rows", [])]

    # ── Signal detection ─────────────────────────────────────

    @staticmethod
    def detect_intent_mismatch(data: dict) -> bool:
        imp = data.get("impressions", 0)
        clicks = data.get("clicks", 0)
        ctr = data.get("ctr", 0)
        pos = data.get("position", 50)

        if imp > 1000 and ctr < 1.5:
            return True
        if imp > 500 and clicks < 3:
            return True
        if pos and pos <= 10 and ctr < 2.0:
            return True
        return False
