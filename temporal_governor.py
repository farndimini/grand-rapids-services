"""
temporal_governor.py — Real-Time Temporal Governance Engine
=============================================================
Enforces temporal policies on all published articles:
  - Detects expired claims (price, stats, recommendations)
  - Detects stale statistics (old years, outdated data)
  - Detects old pricing (prices that likely changed)
  - Detects outdated recommendations
  - Detects citation freshness collapse
  - Automatic quarantine of stale articles
  - Scheduled re-verification
  - Freshness SLA enforcement
  - Decay alerts

Architecture:
  TemporalGovernor
    ├── ExpiryPolicy (rules for what triggers expiry)
    ├── FreshnessPolicy (freshness SLA thresholds)
    ├── CitationDecayMonitor (citation-level freshness)
    ├── StaleArticleScanner (scans existing articles)
    └── DecayAlertSystem (emits alerts on decay)
"""

from __future__ import annotations

import re
import json
import time
import math
import os
import hashlib
import logging
from typing import Any, Optional
from pathlib import Path
from dataclasses import dataclass, field

log = logging.getLogger("temporal_governor")

GOVERNOR_STORE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "governor_store")


def _ensure_store():
    Path(GOVERNOR_STORE_DIR).mkdir(parents=True, exist_ok=True)


def _jsonl_append(filename: str, record: dict) -> None:
    _ensure_store()
    path = os.path.join(GOVERNOR_STORE_DIR, filename)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except OSError as e:
        log.error("Failed to write %s: %s", filename, e)


def _jsonl_read(filename: str) -> list[dict]:
    _ensure_store()
    path = os.path.join(GOVERNOR_STORE_DIR, filename)
    if not os.path.exists(path):
        return []
    records = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except OSError:
        return []
    return records


# ── Data Classes ─────────────────────────────────────────

@dataclass
class ExpiredClaim:
    """A claim that has expired according to policy."""
    claim_id: str
    claim_text: str
    claim_type: str
    keyword: str
    policy_name: str
    expiry_reason: str
    age_days: float
    original_confidence: float
    detected_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "claim_type": self.claim_type,
            "keyword": self.keyword,
            "policy_name": self.policy_name,
            "expiry_reason": self.expiry_reason,
            "age_days": round(self.age_days, 1),
            "original_confidence": self.original_confidence,
            "detected_at": self.detected_at or time.time(),
        }


@dataclass
class DecayAlert:
    """An alert generated when decay is detected."""
    alert_type: str  # claim_expired, citation_expired, freshness_collapse, sla_breach
    keyword: str
    severity: str  # info, warning, critical
    message: str
    affected_items: list[str] = field(default_factory=list)
    score: float = 0.0
    created_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "alert_type": self.alert_type,
            "keyword": self.keyword,
            "severity": self.severity,
            "message": self.message,
            "affected_items": list(self.affected_items),
            "score": self.score,
            "created_at": self.created_at or time.time(),
        }


@dataclass
class FreshnessReport:
    """Full freshness report for an article."""
    keyword: str
    overall_freshness: float  # 0.0 (stale) to 1.0 (fresh)
    expired_claims: list[ExpiredClaim] = field(default_factory=list)
    expired_citations: int = 0
    stale_statistics: int = 0
    old_pricing: int = 0
    outdated_recommendations: int = 0
    sla_status: str = "compliant"  # compliant, warning, breached
    alerts: list[DecayAlert] = field(default_factory=list)
    quarantine_recommended: bool = False
    revertification_due_days: int = 0
    scanned_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "overall_freshness": self.overall_freshness,
            "expired_claims": [c.to_dict() for c in self.expired_claims],
            "expired_citations": self.expired_citations,
            "stale_statistics": self.stale_statistics,
            "old_pricing": self.old_pricing,
            "outdated_recommendations": self.outdated_recommendations,
            "sla_status": self.sla_status,
            "alerts": [a.to_dict() for a in self.alerts],
            "quarantine_recommended": self.quarantine_recommended,
            "revertification_due_days": self.revertification_due_days,
            "scanned_at": self.scanned_at,
        }


# ── ExpiryPolicy ─────────────────────────────────────────

class ExpiryPolicy:
    """Defines rules for what triggers claim expiry."""

    # Maximum age in days per claim type before expiry
    DEFAULT_MAX_AGES: dict[str, float] = {
        "price": 90.0,        # pricing changes fast
        "percentage": 180.0,  # statistics go stale
        "year": 365.0,        # year references
        "superlative": 120.0, # "best" changes
        "factual": 180.0,     # general facts
        "recommendation": 90.0,  # recommendations go stale fast
    }

    # Niche adjustments
    NICHE_ADJUSTMENTS: dict[str, dict[str, float]] = {
        "technology": {"price": 60.0, "superlative": 60.0, "recommendation": 60.0},
        "health": {"recommendation": 180.0, "factual": 365.0},
        "legal": {"factual": 365.0, "year": 730.0},
        "finance": {"price": 30.0, "percentage": 90.0},
        "ecommerce": {"price": 60.0, "superlative": 60.0},
    }

    def get_max_age(self, claim_type: str, niche: str = "default") -> float:
        base = self.DEFAULT_MAX_AGES.get(claim_type, 180.0)
        niche_adjust = self.NICHE_ADJUSTMENTS.get(niche, {})
        return niche_adjust.get(claim_type, base)

    def is_expired(self, claim_type: str, age_days: float, niche: str = "default") -> tuple[bool, str]:
        max_age = self.get_max_age(claim_type, niche)
        if age_days > max_age:
            return True, f"Claim type '{claim_type}' exceeded max age {max_age:.0f}d (actual: {age_days:.0f}d)"
        if age_days > max_age * 0.8:
            return False, f"Claim approaching expiry ({age_days:.0f}d / {max_age:.0f}d)"
        return False, ""


# ── FreshnessPolicy ──────────────────────────────────────

class FreshnessPolicy:
    """Defines freshness SLA thresholds."""

    def __init__(
        self,
        min_freshness_score: float = 0.4,
        max_stale_ratio: float = 0.3,
        max_expired_citations: int = 2,
        revertification_interval_days: float = 180.0,
    ):
        self.min_freshness_score = min_freshness_score
        self.max_stale_ratio = max_stale_ratio
        self.max_expired_citations = max_expired_citations
        self.revertification_interval_days = revertification_interval_days

    def check_sla(
        self,
        freshness_score: float,
        stale_ratio: float,
        expired_citations: int,
    ) -> tuple[str, list[str]]:
        """Returns (status, violations)."""
        violations = []
        if freshness_score < self.min_freshness_score:
            violations.append(
                f"Freshness score {freshness_score:.2f} below minimum {self.min_freshness_score}"
            )
        if stale_ratio > self.max_stale_ratio:
            violations.append(
                f"Stale ratio {stale_ratio:.2f} exceeds maximum {self.max_stale_ratio}"
            )
        if expired_citations > self.max_expired_citations:
            violations.append(
                f"Expired citations {expired_citations} exceeds maximum {self.max_expired_citations}"
            )

        if len(violations) >= 2:
            return "breached", violations
        elif violations:
            return "warning", violations
        return "compliant", []


# ── CitationDecayMonitor ─────────────────────────────────

class CitationDecayMonitor:
    """Monitors citation freshness over time."""

    def __init__(self, max_citation_age_days: float = 180.0):
        self.max_citation_age_days = max_citation_age_days
        self._alerts: list[DecayAlert] = []

    def check_citation(
        self,
        url: str,
        extracted_at: float,
        domain: Optional[str] = None,
    ) -> dict:
        age_days = (time.time() - extracted_at) / 86400
        expired = age_days > self.max_citation_age_days
        freshness = max(0.0, 1.0 - age_days / self.max_citation_age_days)

        return {
            "url": url,
            "domain": domain or "unknown",
            "age_days": round(age_days, 1),
            "expired": expired,
            "freshness": round(freshness, 3),
            "action": "expired" if expired else "valid",
        }

    def check_citations_batch(self, citations: list[dict]) -> list[dict]:
        return [self.check_citation(
            c.get("url", ""),
            c.get("extracted_at", time.time()),
            c.get("domain"),
        ) for c in citations]

    def get_alerts(self) -> list[DecayAlert]:
        return list(self._alerts)


# ── StaleArticleScanner ──────────────────────────────────

class StaleArticleScanner:
    """Scans articles for stale content patterns."""

    PRICE_RX = re.compile(r"\$[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?")
    YEAR_RX = re.compile(r"\b(?:19|20)[0-9]{2}\b")
    PCT_RX = re.compile(r"\b[0-9]{1,3}%")

    OLD_YEAR_THRESHOLD = 2024

    STALE_PATTERNS = [
        "as of 2020", "as of 2021", "as of 2022", "as of 2023",
        "in 2020", "in 2021", "in 2022", "in 2023",
        "last year", "a few years ago",
        "traditionally", "historically", "formerly",
    ]

    RECOMMENDATION_PATTERNS = [
        "we recommend", "top pick", "best choice",
        "our top", "editor's choice", "highly recommend",
    ]

    def scan(self, article: str, keyword: str, niche: str = "default",
             claims: Optional[list[dict]] = None) -> FreshnessReport:
        existing_claims = claims or []
        report = FreshnessReport(
            keyword=keyword,
            overall_freshness=1.0,
            scanned_at=time.time(),
        )

        text_no_html = re.sub(r"<[^>]+>", " ", article)
        lower = text_no_html.lower()

        # 1. Check for old years
        years = self.YEAR_RX.findall(text_no_html)
        old_years = [y for y in years if int(y) < self.OLD_YEAR_THRESHOLD]
        for y in old_years[:5]:
            report.stale_statistics += 1
            claim_id = hashlib.sha256(f"year:{y}:{keyword}".encode()).hexdigest()[:12]
            report.expired_claims.append(ExpiredClaim(
                claim_id=claim_id,
                claim_text=y,
                claim_type="year",
                keyword=keyword,
                policy_name="stale_year",
                expiry_reason=f"Year {y} is older than threshold {self.OLD_YEAR_THRESHOLD}",
                age_days=(time.time() - self._year_to_timestamp(int(y))) / 86400,
                original_confidence=0.5,
            ))

        # 2. Check for old prices
        prices = self.PRICE_RX.findall(text_no_html)
        if prices:
            # Prices with no uncertainty qualifiers are suspect after 90 days
            report.old_pricing = min(len(prices), len(prices))

        # 3. Check for stale patterns
        for pattern in self.STALE_PATTERNS:
            if pattern in lower:
                claim_id = hashlib.sha256(f"stale:{pattern}:{keyword}".encode()).hexdigest()[:12]
                report.expired_claims.append(ExpiredClaim(
                    claim_id=claim_id,
                    claim_text=pattern,
                    claim_type="factual",
                    keyword=keyword,
                    policy_name="stale_pattern",
                    expiry_reason=f"Stale temporal pattern: '{pattern}'",
                    age_days=0,
                    original_confidence=0.3,
                ))

        # 4. Check for outdated recommendations
        for pattern in self.RECOMMENDATION_PATTERNS:
            if pattern in lower:
                claim_id = hashlib.sha256(f"rec:{pattern}:{keyword}".encode()).hexdigest()[:12]
                report.outdated_recommendations += 1
                report.expired_claims.append(ExpiredClaim(
                    claim_id=claim_id,
                    claim_text=pattern,
                    claim_type="recommendation",
                    keyword=keyword,
                    policy_name="outdated_recommendation",
                    expiry_reason=f"Potentially outdated recommendation pattern: '{pattern}'",
                    age_days=0,
                    original_confidence=0.4,
                ))

        # 5. Check incorporated claims
        for claim in existing_claims:
            claim_type = claim.get("claim_type", "factual")
            age_days = claim.get("age_days", 0)
            if isinstance(age_days, (int, float)) and age_days > 0:
                policy = ExpiryPolicy()
                expired, reason = policy.is_expired(claim_type, age_days, niche)
                if expired:
                    report.expired_claims.append(ExpiredClaim(
                        claim_id=claim.get("id", "unknown"),
                        claim_text=claim.get("text", ""),
                        claim_type=claim_type,
                        keyword=keyword,
                        policy_name="claim_expiry",
                        expiry_reason=reason,
                        age_days=age_days,
                        original_confidence=claim.get("confidence", 0.5),
                    ))

        # Compute overall freshness
        total_issues = (
            report.stale_statistics +
            report.old_pricing +
            report.outdated_recommendations +
            len(report.expired_claims)
        )
        report.overall_freshness = max(0.0, 1.0 - total_issues * 0.1)
        report.overall_freshness = max(0.05, min(1.0, report.overall_freshness))

        # SLA check
        sla = FreshnessPolicy()
        total_claims = max(1, len(existing_claims) + 1)
        stale_ratio = len(report.expired_claims) / total_claims
        sla_status, sla_violations = sla.check_sla(
            report.overall_freshness,
            stale_ratio,
            report.expired_citations,
        )
        report.sla_status = sla_status

        # Generate alerts
        if sla_status == "breached":
            report.alerts.append(DecayAlert(
                alert_type="sla_breach",
                keyword=keyword,
                severity="critical",
                message=f"Freshness SLA breached: {'; '.join(sla_violations[:3])}",
                affected_items=[c.claim_text for c in report.expired_claims[:5]],
                score=report.overall_freshness,
            ))
            report.quarantine_recommended = True
        elif sla_status == "warning":
            report.alerts.append(DecayAlert(
                alert_type="freshness_collapse",
                keyword=keyword,
                severity="warning",
                message=f"Freshness declining: {'; '.join(sla_violations[:2])}",
                score=report.overall_freshness,
            ))

        if report.expired_claims:
            report.alerts.append(DecayAlert(
                alert_type="claim_expired",
                keyword=keyword,
                severity="warning",
                message=f"{len(report.expired_claims)} expired claims detected",
                affected_items=[c.claim_text for c in report.expired_claims[:5]],
                score=report.overall_freshness,
            ))

        # Re-verification due
        if sla_status == "warning":
            report.revertification_due_days = 30
        elif sla_status == "breached":
            report.revertification_due_days = 7
        else:
            report.revertification_due_days = 90

        return report

    def _year_to_timestamp(self, year: int) -> float:
        """Approximate timestamp for a year. Avoids mktime for portability."""
        EPOCH_YEAR = 1970
        SECONDS_PER_YEAR = 365.25 * 86400
        return (year - EPOCH_YEAR) * SECONDS_PER_YEAR


# ── DecayAlertSystem ─────────────────────────────────────

class DecayAlertSystem:
    """Manages decay alerts with persistence."""
    ALERTS_FILE = "decay_alerts.jsonl"

    def record_alert(self, alert: DecayAlert) -> None:
        _jsonl_append(self.ALERTS_FILE, alert.to_dict())

    def get_alerts(self, keyword: Optional[str] = None,
                   severity: Optional[str] = None,
                   limit: int = 100) -> list[DecayAlert]:
        alerts = [DecayAlert(**d) for d in _jsonl_read(self.ALERTS_FILE)]
        if keyword:
            alerts = [a for a in alerts if a.keyword == keyword]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return sorted(alerts, key=lambda a: a.created_at, reverse=True)[:limit]

    def get_stats(self) -> dict:
        alerts = [DecayAlert(**d) for d in _jsonl_read(self.ALERTS_FILE)]
        severity_counts = {}
        type_counts = {}
        for a in alerts:
            severity_counts[a.severity] = severity_counts.get(a.severity, 0) + 1
            type_counts[a.alert_type] = type_counts.get(a.alert_type, 0) + 1
        return {
            "total_alerts": len(alerts),
            "by_severity": severity_counts,
            "by_type": type_counts,
        }


# ── TemporalGovernor ─────────────────────────────────────

class TemporalGovernor:
    """Central temporal governance engine.

    Enforces expiry policies, freshness SLAs, and generates
    quarantine recommendations for stale articles.
    """

    def __init__(self):
        self.expiry_policy = ExpiryPolicy()
        self.freshness_policy = FreshnessPolicy()
        self.citation_monitor = CitationDecayMonitor()
        self.scanner = StaleArticleScanner()
        self.alert_system = DecayAlertSystem()

    def audit_article(
        self,
        article: str,
        keyword: str,
        niche: str = "default",
        claims: Optional[list[dict]] = None,
        citations: Optional[list[dict]] = None,
    ) -> FreshnessReport:
        """Run full temporal governance audit on an article."""
        # Scan for stale content
        report = self.scanner.scan(article, keyword, niche, claims)

        # Check citations
        if citations:
            citation_results = self.citation_monitor.check_citations_batch(citations)
            report.expired_citations = sum(1 for c in citation_results if c.get("expired"))
            if report.expired_citations > 0:
                report.alerts.append(DecayAlert(
                    alert_type="citation_expired",
                    keyword=keyword,
                    severity="warning",
                    message=f"{report.expired_citations} expired citations detected",
                    affected_items=[c.get("url", "") for c in citation_results if c.get("expired")][:5],
                    score=report.overall_freshness,
                ))

        # SLA enforcement
        total_claims = max(1, len(claims or []) + 1)
        stale_ratio = len(report.expired_claims) / total_claims
        sla_status, sla_violations = self.freshness_policy.check_sla(
            report.overall_freshness,
            stale_ratio,
            report.expired_citations,
        )
        report.sla_status = sla_status

        if sla_status in ("breached", "warning"):
            report.quarantine_recommended = sla_status == "breached"

        # Persist alerts
        for alert in report.alerts:
            self.alert_system.record_alert(alert)

        return report

    def get_quarantine_candidates(self, articles: list[dict]) -> list[dict]:
        """Scan multiple articles and return those needing quarantine."""
        candidates = []
        for article_data in articles:
            report = self.audit_article(
                article=article_data.get("article", ""),
                keyword=article_data.get("keyword", ""),
                niche=article_data.get("niche", "default"),
                claims=article_data.get("claims"),
                citations=article_data.get("citations"),
            )
            if report.quarantine_recommended:
                candidates.append({
                    "keyword": article_data.get("keyword"),
                    "freshness": report.overall_freshness,
                    "expired_claims": len(report.expired_claims),
                    "sla_status": report.sla_status,
                    "report": report.to_dict(),
                })
        return candidates

    def get_stats(self) -> dict:
        return {
            "alert_stats": self.alert_system.get_stats(),
        }


# ── Global Singleton ─────────────────────────────────────

_GOVERNOR: Optional[TemporalGovernor] = None


def get_temporal_governor() -> TemporalGovernor:
    global _GOVERNOR
    if _GOVERNOR is None:
        _GOVERNOR = TemporalGovernor()
    return _GOVERNOR


def reset_temporal_governor() -> None:
    global _GOVERNOR
    _GOVERNOR = None


def run_temporal_governance(
    article: str,
    keyword: str,
    niche: str = "default",
    claims: Optional[list[dict]] = None,
    citations: Optional[list[dict]] = None,
) -> FreshnessReport:
    """Quick-access: run full temporal governance audit."""
    governor = get_temporal_governor()
    return governor.audit_article(article, keyword, niche, claims, citations)
