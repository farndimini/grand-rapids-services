"""
truth_infrastructure.py — Enterprise Truth Infrastructure
===========================================================
Persistent truth layer with 6 pillars:

1. كل claim يصبح node دائم   → TruthNode (persistent claim registry)
2. كل citation يصبح lineage   → CitationLineage (full provenance)
3. كل مصدر يحصل freshness     → FreshnessScorer (temporal scoring)
4. كل contradiction يُخزن     → ContradictionHistory (historical tracking)
5. كل repair يُسجل كتعلم      → RepairRecord (permanent learning)
6. كل hallucination signal    → HallucinationSignal (training data)
"""

from __future__ import annotations

import json
import time
import os
import re
import hashlib
import logging
from typing import Any, Optional
from pathlib import Path

log = logging.getLogger("truth_infra")

TRUTH_STORE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "truth_store")


# ── Ensure store directory ───────────────────────────────

def _ensure_store():
    Path(TRUTH_STORE_DIR).mkdir(parents=True, exist_ok=True)


# ── JSONL helpers ─────────────────────────────────────────

def _jsonl_append(filename: str, record: dict) -> None:
    _ensure_store()
    path = os.path.join(TRUTH_STORE_DIR, filename)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except OSError as e:
        log.error("Failed to write %s: %s", filename, e)


def _jsonl_read(filename: str) -> list[dict]:
    _ensure_store()
    path = os.path.join(TRUTH_STORE_DIR, filename)
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


# ── 1. TruthNode ─────────────────────────────────────────

class TruthNode:
    """Permanent claim node — requirement #1.

    Every claim becomes a persistent, traceable, immutable node.
    """

    def __init__(
        self,
        text: str,
        claim_type: str = "factual",
        confidence: float = 0.5,
        source_url: Optional[str] = None,
        keyword: Optional[str] = None,
        article_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ):
        self.id = self._make_id(text, keyword or "")
        self.text = text
        self.claim_type = claim_type
        self.confidence = max(0.0, min(1.0, confidence))
        self.source_url = source_url
        self.keyword = keyword
        self.article_id = article_id
        self.created_at = time.time()
        self.updated_at = self.created_at
        self.verifier_score: Optional[float] = None
        self.verifier_name: Optional[str] = None
        self.serp_consensus: float = 0.0
        self.is_contradicted: bool = False
        self.is_hallucination: bool = False
        self.metadata = metadata or {}

    @staticmethod
    def _make_id(text: str, keyword: str) -> str:
        raw = f"{text.strip().lower()[:200]}|{keyword.strip().lower()[:50]}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "claim_type": self.claim_type,
            "confidence": self.confidence,
            "source_url": self.source_url,
            "keyword": self.keyword,
            "article_id": self.article_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "verifier_score": self.verifier_score,
            "verifier_name": self.verifier_name,
            "serp_consensus": self.serp_consensus,
            "is_contradicted": self.is_contradicted,
            "is_hallucination": self.is_hallucination,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: dict) -> TruthNode:
        node = cls(
            text=d["text"],
            claim_type=d.get("claim_type", "factual"),
            confidence=d.get("confidence", 0.5),
            source_url=d.get("source_url"),
            keyword=d.get("keyword"),
            article_id=d.get("article_id"),
            metadata=d.get("metadata"),
        )
        node.id = d["id"]
        node.created_at = d.get("created_at", time.time())
        node.updated_at = d.get("updated_at", time.time())
        node.verifier_score = d.get("verifier_score")
        node.verifier_name = d.get("verifier_name")
        node.serp_consensus = d.get("serp_consensus", 0.0)
        node.is_contradicted = d.get("is_contradicted", False)
        node.is_hallucination = d.get("is_hallucination", False)
        return node

    def __repr__(self) -> str:
        return f"TruthNode({self.id[:8]}..., {self.claim_type}, conf={self.confidence:.2f})"


# ── 2. CitationLineage ────────────────────────────────────

class CitationLineage:
    """Full citation provenance — requirement #2.

    Every citation is a first-class object with URL, domain, title,
    extraction timestamp, freshness score, and citation count.
    """

    def __init__(
        self,
        url: str,
        domain: Optional[str] = None,
        title: Optional[str] = None,
        snippet: Optional[str] = None,
        keyword: Optional[str] = None,
        claim_id: Optional[str] = None,
    ):
        self.id = self._make_id(url)
        self.url = url
        self.domain = domain or self._extract_domain(url)
        self.title = title
        self.snippet = snippet
        self.keyword = keyword
        self.claim_id = claim_id
        self.extracted_at = time.time()
        self.freshness_score: float = 1.0
        self.citation_count: int = 1
        self.is_verified: bool = False
        self.last_verified_at: Optional[float] = None

    @staticmethod
    def _extract_domain(url: str) -> str:
        m = re.match(r"https?://(?:www\.)?([^/]+)", url)
        return m.group(1) if m else url

    @staticmethod
    def _make_id(url: str) -> str:
        return hashlib.sha256(url.strip().lower().encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "domain": self.domain,
            "title": self.title,
            "snippet": self.snippet,
            "keyword": self.keyword,
            "claim_id": self.claim_id,
            "extracted_at": self.extracted_at,
            "freshness_score": self.freshness_score,
            "citation_count": self.citation_count,
            "is_verified": self.is_verified,
            "last_verified_at": self.last_verified_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> CitationLineage:
        cl = cls(
            url=d["url"],
            domain=d.get("domain"),
            title=d.get("title"),
            snippet=d.get("snippet"),
            keyword=d.get("keyword"),
            claim_id=d.get("claim_id"),
        )
        cl.id = d["id"]
        cl.extracted_at = d.get("extracted_at", time.time())
        cl.freshness_score = d.get("freshness_score", 1.0)
        cl.citation_count = d.get("citation_count", 1)
        cl.is_verified = d.get("is_verified", False)
        cl.last_verified_at = d.get("last_verified_at")
        return cl

    def __repr__(self) -> str:
        return f"CitationLineage({self.domain}, freshness={self.freshness_score:.2f})"


# ── 3. FreshnessScorer ────────────────────────────────────

class FreshnessScorer:
    """Temporal freshness scoring — requirement #3.

    Every source receives a freshness score based on:
    - Age (days since extraction)
    - Source domain authority (baseline)
    - Verification status
    """

    DOMAIN_TRUST: dict[str, float] = {
        ".gov": 0.95,
        ".edu": 0.90,
        ".org": 0.75,
        ".com": 0.60,
        ".net": 0.50,
        ".io": 0.45,
    }

    def __init__(self, decay_days: float = 90.0):
        self.decay_days = decay_days

    def score(self, citation: CitationLineage, now: Optional[float] = None) -> float:
        now = now or time.time()
        age_days = (now - citation.extracted_at) / 86400

        # Base from domain trust
        domain_base = 0.5
        for suffix, trust in self.DOMAIN_TRUST.items():
            if citation.domain and citation.domain.endswith(suffix):
                domain_base = trust
                break

        # Age decay: linear to 0 over decay_days
        age_factor = max(0.0, 1.0 - age_days / self.decay_days)

        # Verification bonus
        verif_bonus = 0.1 if citation.is_verified else -0.1

        return max(0.0, min(1.0, 0.4 * domain_base + 0.4 * age_factor + 0.2 * (0.5 + verif_bonus)))

    def score_url(self, url: str, age_days: float) -> float:
        domain = CitationLineage._extract_domain(url) if "://" in url else url
        base = 0.5
        for suffix, trust in self.DOMAIN_TRUST.items():
            if domain.endswith(suffix):
                base = trust
                break
        age_factor = max(0.0, 1.0 - age_days / self.decay_days)
        return max(0.0, min(1.0, 0.6 * base + 0.4 * age_factor))

    def score_text(self, text: str) -> float:
        """Score a claim text for freshness indicators."""
        lower = text.lower()
        indicators = {
            "as of 202": 0.9,
            "2025": 0.7,
            "2026": 0.95,
            "recent study": 0.8,
            "according to": 0.6,
            "estimated": 0.5,
            "approximately": 0.4,
        }
        max_score = 0.3  # baseline
        for phrase, boost in indicators.items():
            if phrase in lower:
                max_score = max(max_score, boost)
        return max_score


# ── 4. ContradictionHistory ────────────────────────────────

class ContradictionRecord:
    """A recorded contradiction event between two claims."""

    def __init__(
        self,
        claim_a_id: str,
        claim_b_id: str,
        claim_a_text: str,
        claim_b_text: str,
        keyword: Optional[str] = None,
        resolution: Optional[str] = None,
    ):
        self.id = hashlib.sha256(
            f"{claim_a_id}:{claim_b_id}".encode()
        ).hexdigest()[:16]
        self.claim_a_id = claim_a_id
        self.claim_b_id = claim_b_id
        self.claim_a_text = claim_a_text
        self.claim_b_text = claim_b_text
        self.keyword = keyword
        self.detected_at = time.time()
        self.resolution = resolution  # None, claim_a_wins, claim_b_wins, both_removed
        self.resolved_at: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "claim_a_id": self.claim_a_id,
            "claim_b_id": self.claim_b_id,
            "claim_a_text": self.claim_a_text,
            "claim_b_text": self.claim_b_text,
            "keyword": self.keyword,
            "detected_at": self.detected_at,
            "resolution": self.resolution,
            "resolved_at": self.resolved_at,
        }


class ContradictionHistory:
    """Historical contradiction tracking — requirement #4.

    Every contradiction is stored with full context and can be
    resolved, queried, and analyzed for patterns.
    """

    CONTRADICTIONS_FILE = "contradiction_history.jsonl"

    def record(self, record: ContradictionRecord) -> None:
        _jsonl_append(self.CONTRADICTIONS_FILE, record.to_dict())

    def get_all(self) -> list[ContradictionRecord]:
        records = []
        for d in _jsonl_read(self.CONTRADICTIONS_FILE):
            r = ContradictionRecord(
                claim_a_id=d["claim_a_id"],
                claim_b_id=d["claim_b_id"],
                claim_a_text=d["claim_a_text"],
                claim_b_text=d["claim_b_text"],
                keyword=d.get("keyword"),
                resolution=d.get("resolution"),
            )
            r.id = d["id"]
            r.detected_at = d.get("detected_at", 0)
            r.resolved_at = d.get("resolved_at")
            records.append(r)
        return records

    def get_unresolved(self) -> list[ContradictionRecord]:
        return [r for r in self.get_all() if r.resolution is None]

    def resolve(self, record_id: str, resolution: str) -> bool:
        records = _jsonl_read(self.CONTRADICTIONS_FILE)
        updated = False
        new_records = []
        for d in records:
            if d.get("id") == record_id:
                d["resolution"] = resolution
                d["resolved_at"] = time.time()
                updated = True
            new_records.append(d)
        if updated:
            _ensure_store()
            path = os.path.join(TRUTH_STORE_DIR, self.CONTRADICTIONS_FILE)
            try:
                with open(path, "w", encoding="utf-8") as f:
                    for r in new_records:
                        f.write(json.dumps(r, default=str) + "\n")
            except OSError as e:
                log.error("Failed to update contradictions: %s", e)
        return updated

    def count(self) -> dict:
        all_recs = self.get_all()
        unresolved = [r for r in all_recs if r.resolution is None]
        return {
            "total": len(all_recs),
            "unresolved": len(unresolved),
            "resolved": len(all_recs) - len(unresolved),
        }


# ── 5. RepairRecord ───────────────────────────────────────

class RepairRecord:
    """Permanent repair learning — requirement #5.

    Every repair is recorded as permanent knowledge that the
    system can learn from across restarts.
    """

    REPAIRS_FILE = "repair_history.jsonl"

    def __init__(
        self,
        keyword: str,
        failure_reason: str,
        failure_class: str,
        repair_prompt: str,
        repair_success: bool,
        article_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
    ):
        self.id = hashlib.sha256(
            f"{keyword}:{failure_reason}:{time.time()}".encode()
        ).hexdigest()[:16]
        self.keyword = keyword
        self.failure_reason = failure_reason
        self.failure_class = failure_class
        self.repair_prompt = repair_prompt
        self.repair_success = repair_success
        self.article_id = article_id
        self.duration_ms = duration_ms
        self.created_at = time.time()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "keyword": self.keyword,
            "failure_reason": self.failure_reason,
            "failure_class": self.failure_class,
            "repair_prompt": self.repair_prompt,
            "repair_success": self.repair_success,
            "article_id": self.article_id,
            "duration_ms": self.duration_ms,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> RepairRecord:
        r = cls(
            keyword=d["keyword"],
            failure_reason=d["failure_reason"],
            failure_class=d.get("failure_class", "unknown"),
            repair_prompt=d.get("repair_prompt", ""),
            repair_success=d.get("repair_success", False),
            article_id=d.get("article_id"),
            duration_ms=d.get("duration_ms"),
        )
        r.id = d["id"]
        r.created_at = d.get("created_at", time.time())
        return r


class RepairHistory:
    """Persistent repair history store."""

    def save(self, record: RepairRecord) -> None:
        _jsonl_append(RepairRecord.REPAIRS_FILE, record.to_dict())

    def get_all(self) -> list[RepairRecord]:
        return [RepairRecord.from_dict(d) for d in _jsonl_read(RepairRecord.REPAIRS_FILE)]

    def get_by_keyword(self, keyword: str) -> list[RepairRecord]:
        return [r for r in self.get_all() if r.keyword == keyword]

    def get_stats(self) -> dict:
        all_recs = self.get_all()
        total = len(all_recs)
        successes = sum(1 for r in all_recs if r.repair_success)
        failures = total - successes
        return {
            "total_repairs": total,
            "successful_repairs": successes,
            "failed_repairs": failures,
            "success_rate": successes / max(1, total),
        }


# ── 6. HallucinationSignal ────────────────────────────────

class HallucinationSignal:
    """Training signal from hallucinations — requirement #6.

    Every detected hallucination becomes a structured training
    signal for future avoidance.
    """

    SIGNALS_FILE = "hallucination_signals.jsonl"

    def __init__(
        self,
        keyword: str,
        claim_text: str,
        confidence: float,
        detected_by: str,
        action_taken: str,
        article_id: Optional[str] = None,
    ):
        self.id = hashlib.sha256(
            f"{keyword}:{claim_text}:{time.time()}".encode()
        ).hexdigest()[:16]
        self.keyword = keyword
        self.claim_text = claim_text
        self.confidence = confidence
        self.detected_by = detected_by
        self.action_taken = action_taken
        self.article_id = article_id
        self.detected_at = time.time()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "keyword": self.keyword,
            "claim_text": self.claim_text,
            "confidence": self.confidence,
            "detected_by": self.detected_by,
            "action_taken": self.action_taken,
            "article_id": self.article_id,
            "detected_at": self.detected_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> HallucinationSignal:
        s = cls(
            keyword=d["keyword"],
            claim_text=d["claim_text"],
            confidence=d.get("confidence", 0.0),
            detected_by=d.get("detected_by", "unknown"),
            action_taken=d.get("action_taken", "none"),
            article_id=d.get("article_id"),
        )
        s.id = d["id"]
        s.detected_at = d.get("detected_at", time.time())
        return s


class HallucinationSignalStore:
    """Persistent hallucination signal store."""

    def save(self, signal: HallucinationSignal) -> None:
        _jsonl_append(HallucinationSignal.SIGNALS_FILE, signal.to_dict())

    def get_all(self) -> list[HallucinationSignal]:
        return [HallucinationSignal.from_dict(d) for d in _jsonl_read(HallucinationSignal.SIGNALS_FILE)]

    def get_by_detector(self, detector: str) -> list[HallucinationSignal]:
        return [s for s in self.get_all() if s.detected_by == detector]

    def get_stats(self) -> dict:
        all_sigs = self.get_all()
        detectors: dict[str, int] = {}
        for s in all_sigs:
            detectors[s.detected_by] = detectors.get(s.detected_by, 0) + 1
        return {
            "total_signals": len(all_sigs),
            "by_detector": detectors,
        }


# ── TruthStore ─────────────────────────────────────────────

class TruthStore:
    """Central persistent store for all truth infrastructure.

    Coordinates all 6 pillars:
    - TruthNode persistence
    - CitationLineage persistence
    - ContradictionHistory
    - RepairHistory
    - HallucinationSignalStore
    - FreshnessScorer
    """

    TRUTH_NODES_FILE = "truth_nodes.jsonl"
    CITATIONS_FILE = "citations.jsonl"

    def __init__(self):
        self.contradictions = ContradictionHistory()
        self.repairs = RepairHistory()
        self.hallucinations = HallucinationSignalStore()
        self.freshness = FreshnessScorer()
        _ensure_store()

    # ── TruthNodes ──

    def save_truth_node(self, node: TruthNode) -> None:
        self._upsert(self.TRUTH_NODES_FILE, node.to_dict(), key="id")

    def load_truth_node(self, node_id: str) -> Optional[TruthNode]:
        for d in _jsonl_read(self.TRUTH_NODES_FILE):
            if d.get("id") == node_id:
                return TruthNode.from_dict(d)
        return None

    def load_truth_nodes(self, keyword: Optional[str] = None) -> list[TruthNode]:
        nodes = [TruthNode.from_dict(d) for d in _jsonl_read(self.TRUTH_NODES_FILE)]
        if keyword:
            nodes = [n for n in nodes if n.keyword == keyword]
        return nodes

    def search_truth_nodes(self, text: str) -> list[TruthNode]:
        lower = text.lower()
        return [
            TruthNode.from_dict(d) for d in _jsonl_read(self.TRUTH_NODES_FILE)
            if lower in d.get("text", "").lower()
        ]

    # ── Citations ──

    def save_citation(self, citation: CitationLineage) -> None:
        self._upsert(self.CITATIONS_FILE, citation.to_dict(), key="id")

    def load_citation(self, citation_id: str) -> Optional[CitationLineage]:
        for d in _jsonl_read(self.CITATIONS_FILE):
            if d.get("id") == citation_id:
                return CitationLineage.from_dict(d)
        return None

    def load_citations(self, keyword: Optional[str] = None) -> list[CitationLineage]:
        cites = [CitationLineage.from_dict(d) for d in _jsonl_read(self.CITATIONS_FILE)]
        if keyword:
            cites = [c for c in cites if c.keyword == keyword]
        return cites

    def update_citation_freshness(self) -> int:
        """Recompute freshness for all citations. Returns count updated."""
        cites = _jsonl_read(self.CITATIONS_FILE)
        now = time.time()
        updated = 0
        for d in cites:
            cl = CitationLineage.from_dict(d)
            new_score = self.freshness.score(cl, now)
            if abs(new_score - cl.freshness_score) > 0.01:
                cl.freshness_score = new_score
                cl.to_dict().update(d)
                updated += 1
        if updated:
            self._rewrite(self.CITATIONS_FILE, cites)
        return updated

    # ── Stats ──

    def get_stats(self) -> dict:
        nodes = _jsonl_read(self.TRUTH_NODES_FILE)
        cites = _jsonl_read(self.CITATIONS_FILE)
        contra_stats = self.contradictions.count()
        repair_stats = self.repairs.get_stats()
        hallu_stats = self.hallucinations.get_stats()

        # Low-confidence claims
        low_conf = sum(1 for d in nodes if d.get("confidence", 0.5) < 0.4)

        # Contradicted claims
        contradicted = sum(1 for d in nodes if d.get("is_contradicted"))

        return {
            "truth_nodes": len(nodes),
            "citations": len(cites),
            "low_confidence_claims": low_conf,
            "contradicted_claims": contradicted,
            "contradictions": contra_stats,
            "repairs": repair_stats,
            "hallucination_signals": hallu_stats,
        }

    def _upsert(self, filename: str, record: dict, key: str) -> None:
        """Append or update by key."""
        exists = False
        records = _jsonl_read(filename)
        for i, r in enumerate(records):
            if r.get(key) == record.get(key):
                records[i] = record
                exists = True
                break
        if not exists:
            records.append(record)
        self._rewrite(filename, records)

    def _rewrite(self, filename: str, records: list[dict]) -> None:
        _ensure_store()
        path = os.path.join(TRUTH_STORE_DIR, filename)
        try:
            with open(path, "w", encoding="utf-8") as f:
                for r in records:
                    f.write(json.dumps(r, default=str) + "\n")
        except OSError as e:
            log.error("Failed to write %s: %s", filename, e)


# ── Global Singleton ──────────────────────────────────────

_TRUTH: Optional[TruthStore] = None


def get_truth_store() -> TruthStore:
    global _TRUTH
    if _TRUTH is None:
        _TRUTH = TruthStore()
    return _TRUTH


def reset_truth_store() -> None:
    global _TRUTH
    _TRUTH = None


# ── Convenience helpers ───────────────────────────────────

def register_claim(
    text: str,
    claim_type: str = "factual",
    confidence: float = 0.5,
    source_url: Optional[str] = None,
    keyword: Optional[str] = None,
) -> TruthNode:
    """Register a claim as a permanent TruthNode."""
    store = get_truth_store()
    node = TruthNode(
        text=text,
        claim_type=claim_type,
        confidence=confidence,
        source_url=source_url,
        keyword=keyword,
    )
    store.save_truth_node(node)
    return node


def register_citation(
    url: str,
    title: Optional[str] = None,
    snippet: Optional[str] = None,
    keyword: Optional[str] = None,
    claim_id: Optional[str] = None,
) -> CitationLineage:
    """Register a citation with full lineage."""
    store = get_truth_store()
    citation = CitationLineage(
        url=url,
        title=title,
        snippet=snippet,
        keyword=keyword,
        claim_id=claim_id,
    )
    citation.freshness_score = store.freshness.score(citation)
    store.save_citation(citation)
    return citation


def record_contradiction(
    claim_a_text: str,
    claim_b_text: str,
    claim_a_id: str,
    claim_b_id: str,
    keyword: Optional[str] = None,
) -> ContradictionRecord:
    """Record a contradiction between two claims."""
    store = get_truth_store()
    record = ContradictionRecord(
        claim_a_id=claim_a_id,
        claim_b_id=claim_b_id,
        claim_a_text=claim_a_text,
        claim_b_text=claim_b_text,
        keyword=keyword,
    )
    store.contradictions.record(record)
    return record


def record_repair(
    keyword: str,
    failure_reason: str,
    failure_class: str,
    repair_prompt: str,
    repair_success: bool,
) -> RepairRecord:
    """Record a repair attempt as permanent learning."""
    store = get_truth_store()
    record = RepairRecord(
        keyword=keyword,
        failure_reason=failure_reason,
        failure_class=failure_class,
        repair_prompt=repair_prompt,
        repair_success=repair_success,
    )
    store.repairs.save(record)
    return record


def record_hallucination(
    keyword: str,
    claim_text: str,
    confidence: float,
    detected_by: str,
    action_taken: str,
) -> HallucinationSignal:
    """Record a hallucination as a training signal."""
    store = get_truth_store()
    signal = HallucinationSignal(
        keyword=keyword,
        claim_text=claim_text,
        confidence=confidence,
        detected_by=detected_by,
        action_taken=action_taken,
    )
    store.hallucinations.save(signal)
    return signal


def get_truth_summary() -> str:
    """Get a human-readable summary of the truth infrastructure."""
    store = get_truth_store()
    stats = store.get_stats()
    lines = [
        "═══ Truth Infrastructure Summary ═══",
        f"  Truth nodes:        {stats['truth_nodes']}",
        f"  Citations:          {stats['citations']}",
        f"  Low-confidence:     {stats['low_confidence_claims']}",
        f"  Contradicted:       {stats['contradicted_claims']}",
        f"  Contradictions:     {stats['contradictions']['total']} total, "
        f"{stats['contradictions']['unresolved']} unresolved",
        f"  Repairs:            {stats['repairs']['total_repairs']} total, "
        f"{stats['repairs']['success_rate']:.0%} success",
        f"  Hallucination sigs: {stats['hallucination_signals']['total_signals']}",
    ]
    return "\n".join(lines)
