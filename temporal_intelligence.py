"""
temporal_intelligence.py — Time-Aware Probabilistic Truth.

T_effective = T_0 * e^(-lambda*t) * F_source * C_consensus
"""
from __future__ import annotations
import time, math, json, hashlib, logging
from typing import Any, Optional
log = logging.getLogger("temporal")

DECAY_LAMBDA_DEFAULT = 0.01
DECAY_LAMBDA_FAST = 0.05
DECAY_LAMBDA_SLOW = 0.003


class TemporalClaim:
    def __init__(self, text: str, claim_type: str = "factual",
                 confidence: float = 0.5, source_url: str = None,
                 keyword: str = None, decay_lambda: float = None):
        self.id = hashlib.sha256(f"{text}|{keyword or ''}".encode()).hexdigest()[:16]
        self.text = text
        self.claim_type = claim_type
        self.confidence = max(0.0, min(1.0, confidence))
        self.source_url = source_url
        self.keyword = keyword
        self.birth_time = time.time()
        self.decay_lambda = decay_lambda or {
            "price": DECAY_LAMBDA_FAST, "percentage": DECAY_LAMBDA_FAST,
            "year": DECAY_LAMBDA_SLOW, "superlative": DECAY_LAMBDA_DEFAULT,
            "factual": DECAY_LAMBDA_DEFAULT,
        }.get(claim_type, DECAY_LAMBDA_DEFAULT)
        self.source_freshness = 1.0
        self.consensus_stability = 1.0
        self.is_expired = False
        self.expired_at = None
        self.metadata = {}

    def age_days(self, now: float = None) -> float:
        return ((now or time.time()) - self.birth_time) / 86400

    def effective_confidence(self, now: float = None) -> float:
        t = self.age_days(now)
        decay = math.exp(-self.decay_lambda * t)
        return max(0.0, min(1.0,
            self.confidence * decay * self.source_freshness * self.consensus_stability))

    def is_stale(self, threshold: float = 0.3, now: float = None) -> bool:
        return self.effective_confidence(now) < threshold

    def to_dict(self) -> dict:
        return {"id": self.id, "text": self.text, "claim_type": self.claim_type,
                "confidence": self.confidence,
                "effective_confidence": self.effective_confidence(),
                "age_days": round(self.age_days(), 1),
                "decay_lambda": self.decay_lambda,
                "source_freshness": self.source_freshness,
                "consensus_stability": self.consensus_stability,
                "is_stale": self.is_stale(), "is_expired": self.is_expired,
                "source_url": self.source_url, "keyword": self.keyword}

    def __repr__(self):
        return f"TemporalClaim({self.id[:8]}..., eff={self.effective_confidence():.2f})"


class FreshnessDecayEngine:
    def __init__(self, default_lambda: float = DECAY_LAMBDA_DEFAULT):
        self.default_lambda = default_lambda

    def decay_claim(self, claim: TemporalClaim, now: float = None) -> dict:
        eff = claim.effective_confidence(now)
        return {"id": claim.id, "text": claim.text,
                "original_confidence": claim.confidence,
                "effective_confidence": eff,
                "age_days": claim.age_days(now),
                "decay_factor": math.exp(-claim.decay_lambda * claim.age_days(now)),
                "stale": claim.is_stale(now=now)}

    def decay_all(self, claims: list[TemporalClaim], now: float = None) -> list[dict]:
        return [self.decay_claim(c, now) for c in claims]

    def adjust_lambda_for_niche(self, niche: str) -> float:
        return {"technology": 0.02, "finance": 0.015, "health": 0.008,
                "legal": 0.005, "ecommerce": 0.015}.get(niche, self.default_lambda)


class CitationExpiryTracker:
    def __init__(self, max_age_days: float = 180.0):
        self.max_age_days = max_age_days
        self._expired = []

    def check_citation(self, url: str, extracted_at: float, domain: str = None) -> dict:
        age_days = (time.time() - extracted_at) / 86400
        expired = age_days > self.max_age_days
        result = {"url": url, "domain": domain or "unknown",
                  "age_days": round(age_days, 1), "expired": expired,
                  "action": "expired [VERIFY]" if expired else "valid"}
        if expired:
            self._expired.append(result)
        return result

    def check_citations_batch(self, citations: list[dict]) -> list[dict]:
        return [self.check_citation(c.get("url", ""), c.get("extracted_at", time.time()),
                                     c.get("domain")) for c in citations]

    def get_expired(self) -> list[dict]:
        return list(self._expired)

    def expire_in_article(self, article: str, citations: list[dict]) -> str:
        modified = article
        for c in citations:
            if c.get("expired"):
                url = c.get("url", "")
                if url and url in modified:
                    modified = modified.replace(url, f"{url} [VERIFY: citation expired]")
        return modified


class TemporalContradictionTracker:
    def __init__(self):
        self._history = []

    def record_contradiction(self, claim_a: str, claim_b: str,
                              claim_a_id: str, claim_b_id: str,
                              keyword: str = None) -> dict:
        record = {"id": hashlib.sha256(f"{claim_a_id}:{claim_b_id}:{time.time()}".encode()
                                        ).hexdigest()[:12],
                  "claim_a_text": claim_a, "claim_b_text": claim_b,
                  "claim_a_id": claim_a_id, "claim_b_id": claim_b_id,
                  "keyword": keyword, "detected_at": time.time(),
                  "resolved": False, "resolution": None}
        self._history.append(record)
        return record

    def get_recent(self, limit: int = 20) -> list[dict]:
        return sorted(self._history, key=lambda r: r["detected_at"], reverse=True)[:limit]

    def get_unresolved(self) -> list[dict]:
        return [r for r in self._history if not r["resolved"]]

    def resolve(self, record_id: str, resolution: str) -> bool:
        for r in self._history:
            if r["id"] == record_id:
                r["resolved"] = True; r["resolution"] = resolution
                r["resolved_at"] = time.time(); return True
        return False

    def contradiction_rate(self, days: int = 30) -> float:
        cutoff = time.time() - days * 86400
        recent = [r for r in self._history if r["detected_at"] > cutoff]
        resolved = sum(1 for r in recent if r["resolved"])
        return resolved / max(1, len(recent))


class RecencyPropagation:
    def propagate(self, claims: list[TemporalClaim],
                   edges: list[tuple[str, str, str]]) -> list[TemporalClaim]:
        claim_map = {c.id: c for c in claims}
        for from_id, to_id, relation in edges:
            src = claim_map.get(from_id)
            tgt = claim_map.get(to_id)
            if not src or not tgt:
                continue
            if relation == "supports":
                tgt.source_freshness = min(1.0, tgt.source_freshness + src.source_freshness * 0.1)
            elif relation == "contradicts":
                src.source_freshness = max(0.0, src.source_freshness - 0.05)
                tgt.source_freshness = max(0.0, tgt.source_freshness - 0.05)
        return claims


class HistoricalTruthSnapshot:
    def __init__(self, keyword: str, claims: list[TemporalClaim]):
        self.keyword = keyword
        self.taken_at = time.time()
        self.claims = [c.to_dict() for c in claims]
        self.avg_confidence = sum(c["effective_confidence"] for c in self.claims) / max(1, len(self.claims))
        self.stale_count = sum(1 for c in self.claims if c.get("is_stale"))
        self.expired_count = sum(1 for c in self.claims if c.get("is_expired"))

    def to_dict(self) -> dict:
        return {"keyword": self.keyword, "taken_at": self.taken_at,
                "claim_count": len(self.claims), "avg_confidence": self.avg_confidence,
                "stale_count": self.stale_count, "expired_count": self.expired_count}


class HistoricalTruthStore:
    def __init__(self):
        self._snapshots = []

    def take_snapshot(self, keyword: str, claims: list[TemporalClaim]) -> HistoricalTruthSnapshot:
        snap = HistoricalTruthSnapshot(keyword, claims)
        self._snapshots.append(snap)
        return snap

    def get_snapshots(self, keyword: str = None) -> list[HistoricalTruthSnapshot]:
        if keyword:
            return [s for s in self._snapshots if s.keyword == keyword]
        return list(self._snapshots)

    def compare(self, newer: HistoricalTruthSnapshot, older: HistoricalTruthSnapshot) -> dict:
        return {"keyword": newer.keyword,
                "time_span_days": round((newer.taken_at - older.taken_at) / 86400, 1),
                "confidence_change": round(newer.avg_confidence - older.avg_confidence, 3),
                "stale_change": newer.stale_count - older.stale_count,
                "expired_change": newer.expired_count - older.expired_count}


class TemporalIntelligenceEngine:
    def __init__(self):
        self.decay = FreshnessDecayEngine()
        self.citations = CitationExpiryTracker()
        self.contradictions = TemporalContradictionTracker()
        self.propagation = RecencyPropagation()
        self.history = HistoricalTruthStore()

    def process_article(self, article: str, keyword: str,
                         claims: list[TemporalClaim] = None,
                         citations: list[dict] = None,
                         dag_edges: list[tuple[str, str, str]] = None,
                         niche: str = "default") -> dict:
        report = {"keyword": keyword, "niche": niche, "timestamp": time.time(),
                   "decayed_claims": [], "expired_citations": [],
                   "contradictions": [], "snapshot": None,
                   "effective_confidence": 0.0}
        if claims:
            report["decayed_claims"] = self.decay.decay_all(claims)
            avg_eff = sum(d["effective_confidence"] for d in report["decayed_claims"])
            report["effective_confidence"] = avg_eff / max(1, len(report["decayed_claims"]))
            if dag_edges:
                self.propagation.propagate(claims, dag_edges)
                report["decayed_claims"] = self.decay.decay_all(claims)
        if citations:
            report["expired_citations"] = self.citations.check_citations_batch(citations)
        if claims:
            snap = self.history.take_snapshot(keyword, claims)
            report["snapshot"] = snap.to_dict()
        return report

    def get_summary(self, report: dict) -> str:
        return (f"Temporal: conf={report['effective_confidence']:.3f}, "
                f"decayed={len(report['decayed_claims'])}, "
                f"expired={len(report['expired_citations'])}")


_ENGINE = None
def get_temporal_engine() -> TemporalIntelligenceEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = TemporalIntelligenceEngine()
    return _ENGINE

def reset_temporal_engine():
    global _ENGINE
    _ENGINE = None
