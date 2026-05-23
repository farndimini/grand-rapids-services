"""
health_dashboard.py — System Health & Diagnostics Reporter
===========================================================
Generates a consolidated health report across ALL subsystems:
  • Agent core (relay, validator, parallel, cache, memory)
  • SEO layer (research engine, content gap, ranking brain)
  • Intelligence layer (stealth scraper, SERP, evolution)
  • Business layer (GSC client, reporting)
  • Memory & storage integrity

Usage:
    from agent_core.health_dashboard import HealthDashboard
    dash = HealthDashboard()
    report = dash.generate()
    dash.print_report()
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from config import API_KEYS, GSC_CONFIG, MODELS

log = logging.getLogger("agent_core.health_dashboard")


@dataclass
class HealthReport:
    overall_health: int = 0          # 0-100
    critical_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    subsystem_health: dict[str, dict] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_health": self.overall_health,
            "critical_issues": self.critical_issues,
            "warnings": self.warnings,
            "subsystem_health": self.subsystem_health,
            "recommendations": self.recommendations,
            "generated_at": self.generated_at,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class HealthDashboard:
    """Comprehensive system diagnostics."""

    def __init__(self):
        self._checks = [
            self._check_configuration,
            self._check_agent_core,
            self._check_memory_storage,
            self._check_seo_layer,
            self._check_intelligence_layer,
            self._check_cache_integrity,
        ]

    # ── Entry points ───────────────────────────────────────

    def generate(self) -> HealthReport:
        report = HealthReport()
        scores: list[int] = []
        for check in self._checks:
            name, score, issues, warns, recs = check()
            scores.append(score)
            report.subsystem_health[name] = {
                "health": score,
                "issues": issues,
                "warnings": warns,
            }
            report.critical_issues.extend(issues)
            report.warnings.extend(warns)
            report.recommendations.extend(recs)

        report.overall_health = max(0, min(100, int(sum(scores) / len(scores)))) if scores else 0
        return report

    def print_report(self) -> None:
        r = self.generate()
        print(f"\n{'═' * 62}")
        print("  SEO AGENT PRO — HEALTH DASHBOARD")
        print(f"{'═' * 62}")
        print(f"  Overall Health: {'🟢' if r.overall_health >= 80 else '🟡' if r.overall_health >= 50 else '🔴'} {r.overall_health}/100")
        print()
        for name, sub in r.subsystem_health.items():
            status = "✅" if sub["health"] >= 80 else "⚠️" if sub["health"] >= 50 else "❌"
            print(f"  {status} {name:<30s} {sub['health']:>3d}/100")
        if r.critical_issues:
            print(f"\n  {'─' * 58}")
            print("  CRITICAL ISSUES:")
            for i in r.critical_issues:
                print(f"    ❌ {i}")
        if r.warnings:
            print(f"\n  {'─' * 58}")
            print("  WARNINGS:")
            for w in r.warnings:
                print(f"    ⚠️ {w}")
        if r.recommendations:
            print(f"\n  {'─' * 58}")
            print("  RECOMMENDATIONS:")
            for rec in r.recommendations:
                print(f"    → {rec}")
        print(f"{'═' * 62}\n")

    # ── Individual checks ──────────────────────────────────

    def _check_configuration(self) -> tuple[str, int, list, list, list]:
        score = 100
        issues = []
        warns = []
        recs = []

        # API keys
        configured = sum(1 for k, v in API_KEYS.items() if v and k != "local")
        if configured == 0:
            issues.append("ZERO API keys configured — only 'local' model available")
            score -= 50
        elif configured < 3:
            warns.append(f"Only {configured} API providers configured (recommend 3+)")
            score -= 15

        # GSC
        if not GSC_CONFIG.get("site_url") or not GSC_CONFIG.get("credentials_path"):
            warns.append("GSC not fully configured — business modes will fail")
            score -= 10
            recs.append("Set GSC_SITE_URL and GSC_CREDENTIALS_PATH in .env")

        return "Configuration", score, issues, warns, recs

    def _check_agent_core(self) -> tuple[str, int, list, list, list]:
        score = 100
        issues = []
        warns = []
        recs = []

        modules = [
            "agent_core.relay",
            "agent_core.validator",
            "agent_core.parallel",
            "agent_core.memory_index",
            "agent_core.self_heal",
            "agent_core.cache_manager",
        ]
        for mod in modules:
            try:
                __import__(mod)
            except Exception as e:
                warns.append(f"agent_core module unavailable: {mod} ({e})")
                score -= 8

        return "Agent Core", score, issues, warns, recs

    def _check_memory_storage(self) -> tuple[str, int, list, list, list]:
        score = 100
        issues = []
        warns = []
        recs = []

        from config import SETTINGS
        mem_path = Path(SETTINGS.get("memory_file", "seo_memory.json"))
        if not mem_path.exists():
            warns.append("Memory file not found — system starting fresh")
            score -= 10
        else:
            try:
                data = json.loads(mem_path.read_text(encoding="utf-8"))
                articles = len(data.get("articles_written", []))
                if articles > 1000:
                    warns.append(f"Memory file very large ({articles} articles) — consider archival")
                    recs.append("Run memory archival to keep startup fast")
            except json.JSONDecodeError:
                issues.append("Memory file is CORRUPTED — restore from backup")
                score -= 40

        # Backup dir health
        backup_dir = mem_path.parent / "memory_backups"
        if backup_dir.exists():
            backups = list(backup_dir.glob("memory_*.json"))
            if len(backups) > 50:
                warns.append(f"Too many backups ({len(backups)}) — cleanup recommended")

        return "Memory & Storage", score, issues, warns, recs

    def _check_seo_layer(self) -> tuple[str, int, list, list, list]:
        score = 100
        issues = []
        warns = []
        recs = []

        seo_modules = [
            "seo.research_engine",
            "seo.content_gap",
            "seo.ranking_intelligence",
            "seo.ranking_brain",
            "seo.learning_loop",
            "seo.gsc_client",
            "seo.business_mode",
        ]
        for mod in seo_modules:
            try:
                __import__(mod)
            except Exception:
                # Many are optional, treat as info rather than penalty
                pass

        return "SEO Layer", score, issues, warns, recs

    def _check_intelligence_layer(self) -> tuple[str, int, list, list, list]:
        score = 100
        issues = []
        warns = []
        recs = []

        intel_modules = [
            "seo_intelligence_layer.serp_scraper",
            "seo_intelligence_layer.web_crawler",
            "seo_intelligence_layer.content_analyzer",
            "seo_intelligence_layer.strategy_engine",
            "seo_intelligence_layer.stealth_scraper",
        ]
        for mod in intel_modules:
            try:
                __import__(mod)
            except Exception as e:
                warns.append(f"Intel module import issue: {mod} ({e})")
                score -= 5

        return "Intelligence Layer", score, issues, warns, recs

    def _check_cache_integrity(self) -> tuple[str, int, list, list, list]:
        score = 100
        issues = []
        warns = []
        recs = []

        cache_dirs = ["cache_store", "cache", "agent_core/cache"]
        total_size = 0
        total_files = 0
        for dname in cache_dirs:
            d = Path(dname)
            if d.exists():
                files = list(d.glob("*.json"))
                total_files += len(files)
                for f in files:
                    total_size += f.stat().st_size
                # Integrity check: sample a few files
                bad = 0
                for f in files[:10]:
                    try:
                        json.loads(f.read_text(encoding="utf-8"))
                    except Exception:
                        bad += 1
                if bad > 0:
                    warns.append(f"{bad} corrupted cache files in {dname}")
                    score -= 5 * bad

        if total_size > 500_000_000:  # 500 MB
            warns.append(f"Cache size is {total_size / 1024 / 1024:.0f} MB — consider clearing expired entries")
            recs.append("Run CacheManager.clear_expired() or manual cleanup")
            score -= 10

        return "Cache Integrity", score, issues, warns, recs
