from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from agent_core.gsc_feedback.ranking_history import RankingHistory
from agent_core.gsc_feedback.ctr_tracker import CtrTracker

log = logging.getLogger("gsc_feedback.poller")

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "cache" / "gsc_poller"

POLL_STATE_PATH = Path(__file__).resolve().parent.parent.parent / "cache" / "poller_state.json"


@dataclass
class PollSchedule:
    keyword: str
    interval_minutes: int
    last_poll: str | None = None
    enabled: bool = True


class GscPoller:
    def __init__(self):
        self._ranking_history = RankingHistory()
        self._ctr_tracker = CtrTracker()
        self._lock = threading.RLock()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._load_state()

    def _load_state(self) -> None:
        self._state: dict[str, Any] = {"last_polls": {}}
        if POLL_STATE_PATH.exists():
            try:
                self._state = json.loads(POLL_STATE_PATH.read_text(encoding="utf-8"))
            except Exception:
                log.warning("[POLLER] Failed to load poll state from %s", POLL_STATE_PATH)

    def _save_state(self) -> None:
        with self._lock:
            POLL_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            POLL_STATE_PATH.write_text(
                json.dumps(self._state, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    def poll_keyword(self, keyword: str, days: int = 28) -> dict:
        from config import GSC_CONFIG
        site_url = GSC_CONFIG.get("site_url", "")
        creds_path = GSC_CONFIG.get("credentials_path", "")
        if not site_url or not creds_path or not Path(creds_path).exists():
            return {"keyword": keyword, "error": "GSC not configured", "source": "error"}
        # Validate site URL before trying to connect
        if not site_url.startswith(("https://", "scoped:")):
            return {"keyword": keyword, "error": f"Invalid site URL: {site_url}", "source": "error"}

        data = None
        history = None
        from concurrent.futures import ThreadPoolExecutor, TimeoutError
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            def _fetch():
                from seo.gsc_client import GSCClient
                return GSCClient(site_url=site_url, credentials_path=creds_path).get_keyword_data(keyword, days)
            fut = pool.submit(_fetch)
            data = fut.result(timeout=5)
        except TimeoutError:
            log.warning(f"[POLLER] GSC timeout for '{keyword}'")
            data = {"keyword": keyword, "error": "GSC timeout", "source": "error"}
        except Exception as e:
            log.warning(f"[POLLER] GSC unavailable for '{keyword}': {e}")
            data = {"keyword": keyword, "error": str(e), "source": "error"}
        finally:
            pool.shutdown(wait=True)

        if data is None or "error" in data:
            return data or {"keyword": keyword, "error": "No data", "source": "error"}

        self._ranking_history.add_from_gsc_data(keyword, data)

        if data.get("ctr") is not None:
            self._ctr_tracker.record_ctr(
                keyword=keyword,
                position=data.get("position"),
                ctr=data.get("ctr"),
                impressions=data.get("impressions"),
                clicks=data.get("clicks"),
            )

        for day in (history or []):
            self._ranking_history.add_snapshot(
                keyword=keyword,
                date=day.get("date", ""),
                position=day.get("position"),
                source="gsc_history",
            )

        with self._lock:
            self._state["last_polls"][keyword] = datetime.now().isoformat()
            self._save_state()

        data["_daily_history"] = history
        data["_polled_at"] = datetime.now().isoformat()
        return data

    def poll_top_queries(
        self, max_results: int = 20, days: int = 28
    ) -> list[dict]:
        from config import GSC_CONFIG
        site_url = GSC_CONFIG.get("site_url", "")
        creds_path = GSC_CONFIG.get("credentials_path", "")
        if not site_url or not creds_path or not Path(creds_path).exists():
            return []

        from concurrent.futures import ThreadPoolExecutor, TimeoutError
        pool = ThreadPoolExecutor(max_workers=1)
        try:
            def _fetch_top():
                from seo.gsc_client import GSCClient
                return GSCClient(site_url=site_url, credentials_path=creds_path).get_top_queries(days=days, max_results=max_results)
            fut = pool.submit(_fetch_top)
            queries = fut.result(timeout=5)
        except TimeoutError:
            log.warning("[POLLER] GSC top queries timeout")
            return []
        except Exception as e:
            log.warning(f"[POLLER] GSC top queries unavailable: {e}")
            return []
        finally:
            pool.shutdown(wait=True)

        results = []
        for q in queries:
            kw = q.get("query", "")
            if kw:
                self._ranking_history.add_snapshot(
                    keyword=kw,
                    position=q.get("position"),
                    ctr=q.get("ctr"),
                    impressions=q.get("impressions"),
                    clicks=q.get("clicks"),
                    source="gsc_top_queries",
                )
                results.append(kw)

        with self._lock:
            now = datetime.now().isoformat()
            for kw in results:
                self._state["last_polls"][kw] = now
            self._save_state()

        return results

    def poll_all_tracked(self, days: int = 28) -> dict[str, dict]:
        keywords = self.get_tracked_keywords()
        results = {}
        for kw in keywords:
            results[kw] = self.poll_keyword(kw, days)
        return results

    def get_tracked_keywords(self) -> list[str]:
        return list(self._state.get("last_polls", {}).keys())

    def get_last_poll_time(self, keyword: str) -> str | None:
        return self._state.get("last_polls", {}).get(keyword)

    def mark_tracked(self, keyword: str) -> None:
        with self._lock:
            if keyword not in self._state.get("last_polls", {}):
                self._state.setdefault("last_polls", {})[keyword] = ""
                self._save_state()

    def get_poll_stats(self) -> dict:
        last_polls = self._state.get("last_polls", {})
        now = datetime.now()
        due = []
        for kw, last in last_polls.items():
            if not last:
                due.append(kw)
            else:
                last_dt = datetime.fromisoformat(last)
                if now - last_dt > timedelta(hours=24):
                    due.append(kw)

        return {
            "tracked_keywords": len(last_polls),
            "never_polled": sum(1 for v in last_polls.values() if not v),
            "due_for_poll": len(due),
            "last_poll_counts": {kw: last_polls[kw] for kw in list(last_polls.keys())[:10]},
        }

    def poll_keywords_if_due(
        self, keywords: list[str], max_age_hours: int = 24
    ) -> dict[str, dict]:
        results = {}
        now = datetime.now()
        for kw in keywords:
            last = self.get_last_poll_time(kw)
            if last:
                last_dt = datetime.fromisoformat(last)
                if now - last_dt < timedelta(hours=max_age_hours):
                    continue
            results[kw] = self.poll_keyword(kw)
        return results
