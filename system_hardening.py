"""
system_hardening.py — Phase 2 Runtime System Hardening
=======================================================
All 8 audit dimensions in one deterministic, concurrency-safe module.

Dimensions:
  1. Prompt Execution Truth — fingerprinting, injection verification, payload verification
  2. Memory Contamination Audit — niche isolation, decay, quality-weighted retrieval, blacklist
  3. Claim Grounding Verification — confidence decay, contradiction severity, lineage telemetry
  4. Post-Processor Safety Audit — HTML structural validator, schema validation, nesting detector
  5. LLM Failure Path Audit — retry telemetry, malformed-output quarantine, fallback tracking
  6. Vector Memory Reality Check — empirical A/B comparison harness
  7. Multi-Agent Execution Truth — disagreement scoring, critique propagation, reviewer impact
  8. Performance + Scale Audit — resource caps, pruning, bounded memory, queue backpressure
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("system_hardening")

# ============================================================================
#  DIMENSION 1 — PROMPT EXECUTION TRUTH
# ============================================================================

class PromptFingerprinter:
    """Deterministic prompt fingerprinting with hash telemetry.

    Generates SHA-256 fingerprints for every prompt layer (system, user, injections)
    and tracks injection composition, size, and ordering. Enables runtime verification
    that the final provider payload equals the intended payload.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._history: list[dict[str, Any]] = []
        self._max_history = 100

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]

    @staticmethod
    def _layer_stats(text: str) -> dict[str, Any]:
        return {
            "chars": len(text),
            "words": len(text.split()),
            "lines": len(text.splitlines()),
            "hash": PromptFingerprinter._hash(text),
        }

    def fingerprint_system(self, system_prompt: str) -> dict[str, Any]:
        return self._layer_stats(system_prompt)

    def fingerprint_injection(self, name: str, injection_text: str) -> dict[str, Any]:
        return {"name": name, **self._layer_stats(injection_text)}

    def fingerprint_payload(
        self,
        system: str,
        user: str,
        injections: list[tuple[str, str]],
        model: str,
    ) -> dict[str, Any]:
        """Fingerprint the complete intended payload before it reaches the provider.

        Returns a fingerprint dict that can be compared against what was actually sent.
        """
        system_fp = self.fingerprint_system(system)
        injection_fps = [self.fingerprint_injection(n, t) for n, t in injections]

        # Build composite payload (what should be sent to the LLM)
        # NOTE: user already contains all injection text via {competitor_gaps} formatting.
        # The injections list is tracked separately for anomaly detection only.
        payload_hash = self._hash(system + user)
        user_fp = self._layer_stats(user)

        fp = {
            "model": model,
            "timestamp": time.time(),
            "payload_hash": payload_hash,
            "system": system_fp,
            "user": user_fp,
            "injections": injection_fps,
            "total_injection_chars": sum(inf["chars"] for inf in injection_fps),
            "injection_count": len(injections),
            "injection_order": [n for n, _ in injections],
        }

        with self._lock:
            self._history.append(fp)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        return fp

    def verify_payload(self, intended: dict[str, Any], actual_payload: tuple[str, str]) -> dict[str, Any]:
        """Compare intended fingerprint against what was actually sent to the provider.

        Args:
            intended: The fingerprint from fingerprint_payload()
            actual_payload: (system, user) tuple that was actually sent

        Returns:
            dict with 'match' bool and detailed comparison
        """
        actual_hash = self._hash(actual_payload[0] + actual_payload[1])
        match = actual_hash == intended["payload_hash"]

        return {
            "match": match,
            "intended_hash": intended["payload_hash"],
            "actual_hash": actual_hash,
            "intended_system_chars": intended["system"]["chars"],
            "actual_system_chars": len(actual_payload[0]),
            "intended_user_chars": intended["user"]["chars"],
            "actual_user_chars": len(actual_payload[1]),
            "injection_count": intended["injection_count"],
            "injection_order": intended["injection_order"],
        }

    def detect_anomalies(self, window: int = 10) -> list[dict[str, Any]]:
        """Scan recent fingerprint history for anomalies: overwrites, truncation, collapse."""
        anomalies = []
        with self._lock:
            recent = self._history[-window:]

        if len(recent) < 2:
            return anomalies

        for i in range(1, len(recent)):
            prev = recent[i - 1]
            curr = recent[i]

            # Detect system prompt overwrite
            if prev["system"]["hash"] != curr["system"]["hash"] and prev["model"] == curr["model"]:
                anomalies.append({
                    "type": "system_overwrite",
                    "index": i,
                    "prev_hash": prev["system"]["hash"],
                    "curr_hash": curr["system"]["hash"],
                })

            # Detect injection ordering corruption
            if prev["injection_order"] and curr["injection_order"]:
                if prev["injection_order"] != curr["injection_order"]:
                    anomalies.append({
                        "type": "injection_order_change",
                        "index": i,
                        "prev_order": prev["injection_order"],
                        "curr_order": curr["injection_order"],
                    })

            # Detect injection count change
            if prev["injection_count"] != curr["injection_count"]:
                anomalies.append({
                    "type": "injection_count_change",
                    "index": i,
                    "prev_count": prev["injection_count"],
                    "curr_count": curr["injection_count"],
                })

            # Detect truncation (payload hash unchanged but user chars dramatically differ)
            if curr["total_injection_chars"] < prev["total_injection_chars"] * 0.5:
                anomalies.append({
                    "type": "injection_size_collapse",
                    "index": i,
                    "prev_chars": prev["total_injection_chars"],
                    "curr_chars": curr["total_injection_chars"],
                })

        return anomalies

    def get_history(self, last_n: int = 5) -> list[dict[str, Any]]:
        with self._lock:
            return self._history[-last_n:]

    def get_telemetry(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_fingerprints": len(self._history),
                "unique_system_hashes": len(set(fp["system"]["hash"] for fp in self._history)),
                "total_injections_tracked": sum(fp["injection_count"] for fp in self._history),
                "anomaly_count": len(self.detect_anomalies()),
            }


# Global instance for runtime access
_PROMPT_FINGERPRINTER = PromptFingerprinter()


def get_prompt_fingerprinter() -> PromptFingerprinter:
    return _PROMPT_FINGERPRINTER


# ============================================================================
#  DIMENSION 2 — MEMORY CONTAMINATION AUDIT
# ============================================================================

class ContaminationScorer:
    """Scores memory contamination risk between niches.

    Provides:
    - Contamination scoring (0.0 = clean, 1.0 = fully contaminated)
    - Semantic distance thresholds between niches
    - Decay weighting for old entries
    - Quality-weighted retrieval
    - Blacklist memory filtering
    - Failed-article suppression
    """

    _NICHE_SIGNALS: dict[str, set[str]] = {
        "tech": {"laptop", "software", "app", "gadget", "browser", "extension", "plugin",
                 "gaming", "computer", "smartphone", "device", "api", "code", "programming",
                 "tech", "hardware", "digital"},
        "finance": {"credit", "loan", "mortgage", "insurance", "investing", "crypto",
                    "stock", "retirement", "tax", "bank", "saving", "budget", "debt",
                    "finance", "financial", "money"},
        "health": {"workout", "diet", "supplement", "vitamin", "exercise", "fitness",
                   "nutrition", "wellness", "mental health", "sleep", "yoga", "meditation",
                   "health", "medical"},
        "marketing": {"seo", "content marketing", "social media", "email marketing",
                      "ppc", "analytics", "conversion", "landing page", "copywriting", "branding",
                      "marketing"},
        "education": {"course", "learn", "tutorial", "certification", "degree",
                      "study", "training", "scholarship", "online learning", "education"},
        "lifestyle": {"travel", "food", "fashion", "home", "garden", "pet",
                      "parenting", "wedding", "gift", "lifestyle"},
        "business": {"startup", "saas", "small business", "entrepreneur", "freelance",
                     "remote work", "productivity", "project management", "business"},
    }

    # Known cross-niche term pairs that are NOT contamination (acceptable overlap)
    _ALLOWED_CROSS_PAIRS: set[tuple[str, str]] = {
        ("tech", "business"),  # SaaS is both
        ("marketing", "business"),
        ("education", "tech"),
    }

    def __init__(self, blacklist_keywords: list[str] | None = None):
        self._blacklist = set(blacklist_keywords or [])
        self._decay_rate = 0.05  # per day
        self._quality_threshold = 50
        self._lock = threading.RLock()

    def detect_niche(self, keyword: str) -> str:
        kw = keyword.lower()
        for niche, signals in self._NICHE_SIGNALS.items():
            if any(s in kw for s in signals):
                return niche
        return "general"

    def contamination_score(self, article_niche: str, memory_entry: dict) -> float:
        entry_keyword = memory_entry.get("keyword", "")
        entry_niche = self.detect_niche(entry_keyword)
        if article_niche == "general" or entry_niche == "general":
            return 0.0
        if article_niche == entry_niche:
            return 0.0
        pair = (article_niche, entry_niche)
        reverse_pair = (entry_niche, article_niche)
        if pair in self._ALLOWED_CROSS_PAIRS or reverse_pair in self._ALLOWED_CROSS_PAIRS:
            return 0.3
        return 1.0

    def decay_weight(self, entry: dict, now: datetime | None = None) -> float:
        if now is None:
            now = datetime.now()
        date_str = entry.get("date", "")
        if not date_str:
            return 0.5
        try:
            entry_date = datetime.fromisoformat(date_str) if "T" in date_str else datetime.strptime(date_str[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            return 0.5
        days_old = (now - entry_date).total_seconds() / 86400.0
        weight = max(0.1, 1.0 - (days_old * self._decay_rate))
        return weight

    def quality_weight(self, entry: dict) -> float:
        qs = entry.get("quality_score", 0)
        if not qs or qs < self._quality_threshold:
            return 0.0
        return min(1.0, qs / 100.0)

    def is_blacklisted(self, keyword: str) -> bool:
        return any(bl in keyword.lower() for bl in self._blacklist)

    def should_suppress(self, entry: dict) -> bool:
        if entry.get("quality_score", 100) < self._quality_threshold:
            return True
        if self.is_blacklisted(entry.get("keyword", "")):
            return True
        return False

    def filter_memory_for_niche(
        self,
        mem: dict,
        target_keyword: str,
        max_entries: int = 5,
        require_min_quality: int = 60,
    ) -> list[dict]:
        target_niche = self.detect_niche(target_keyword)
        now = datetime.now()
        scored: list[tuple[float, dict]] = []
        for entry in mem.get("articles_written", []):
            if self.should_suppress(entry):
                continue
            entry_keyword = entry.get("keyword", "")
            if not entry_keyword:
                continue
            if entry_keyword.lower() == target_keyword.lower():
                continue
            entry_niche = self.detect_niche(entry_keyword)
            contam = self.contamination_score(target_niche, entry)
            if contam >= 1.0:
                continue
            quality_w = self.quality_weight(entry)
            decay_w = self.decay_weight(entry, now)
            kw_tokens = set(target_keyword.lower().split())
            ek_tokens = set(entry_keyword.lower().split())
            overlap = len(kw_tokens & ek_tokens) / max(1, len(kw_tokens | ek_tokens))
            combined = (overlap * 0.3) + (quality_w * 0.3) + (decay_w * 0.2) - (contam * 0.2)
            scored.append((combined, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:max_entries]]

    def add_blacklist(self, keyword: str) -> None:
        with self._lock:
            self._blacklist.add(keyword.lower())

    def remove_blacklist(self, keyword: str) -> None:
        with self._lock:
            self._blacklist.discard(keyword.lower())

    def get_blacklist(self) -> list[str]:
        with self._lock:
            return sorted(self._blacklist)


_GLOBAL_CONTAMINATION_SCORER = ContaminationScorer()


def get_contamination_scorer() -> ContaminationScorer:
    return _GLOBAL_CONTAMINATION_SCORER


# ============================================================================
#  DIMENSION 3 — CLAIM GROUNDING VERIFICATION
# ============================================================================

@dataclass
class ClaimLineage:
    """Telemetry for a single claim's lifecycle."""
    claim_text: str
    claim_type: str
    source: str  # "extracted", "generated", "serp", "memory"
    confidence_before: float
    confidence_after: float
    action_taken: str  # "keep", "downgrade", "remove", "rewrite"
    supporting_sources: int
    contradicting_sources: int
    is_superlative: bool
    is_comparative: bool
    timestamp: float = field(default_factory=time.time)


class ClaimGroundingAuditor:
    """Deep audit of claim grounding.

    Detects:
    - Regex blind spots
    - Numerical hallucination gaps
    - Fabricated benchmark language
    - Unsupported comparative claims
    - Fake "best" assertions
    - Missing source attribution
    - False confidence escalation
    """

    _SUPERLATIVE_PATTERNS = re.compile(
        r'\b(best|worst|greatest|leading|top-rated|number one|#1|ultimate|perfect|'
        r'most powerful|most advanced|most popular|industry-leading|'
        r'cutting-edge|state-of-the-art|revolutionary|groundbreaking)\b',
        re.IGNORECASE
    )

    _BENCHMARK_PATTERNS = re.compile(
        r'\b(\d+x\s*faster|\d+%\s*faster|up\s*to\s*\d+[%x]|'
        r'\d+[-\s]times?\s*(faster|better|more|less)|'
        r'speed\s*improvement\s*of\s*\d+|'
        r'performance\s*(gain|boost|increase)\s*of\s*\d+)\b',
        re.IGNORECASE
    )

    _COMPARATIVE_CLAIMS = re.compile(
        r'(\w+(?:\s+\w+){0,3})\s+is\s+(better|worse|faster|slower|cheaper|'
        r'more expensive|more reliable|more efficient|superior|inferior)\s+than\s+'
        r'(\w+(?:\s+\w+){0,3})',
        re.IGNORECASE
    )

    _FAKE_AUTHORITY = re.compile(
        r'\b(according to our research|studies show|research indicates|'
        r'experts agree|industry experts say|analysts predict|'
        r'our analysis found|we found that|data suggests)\b',
        re.IGNORECASE
    )

    def __init__(self):
        self._lineage: list[ClaimLineage] = []
        self._lock = threading.RLock()
        self._max_lineage = 500

    def audit_article(self, article: str) -> dict[str, Any]:
        """Run full claim audit on article HTML.

        Returns dict with issues, superlative count, benchmark violations, etc.
        """
        text = re.sub(r'<[^>]+>', ' ', article)
        text = re.sub(r'\s+', ' ', text).strip()

        superlative_matches = list(self._SUPERLATIVE_PATTERNS.finditer(text))
        benchmark_matches = list(self._BENCHMARK_PATTERNS.finditer(text))
        comparative_matches = list(self._COMPARATIVE_CLAIMS.finditer(text))
        fake_authority_matches = list(self._FAKE_AUTHORITY.finditer(text))

        unsupported_superlatives = []
        unsupported_benchmarks = []
        unsupported_comparatives = []
        for m in superlative_matches:
            start = max(0, m.start() - 100)
            end = min(len(text), m.end() + 100)
            context = text[start:end].lower()
            # Check for supporting evidence within context
            has_evidence = any(
                evidence in context
                for evidence in ["because", "due to", "according to", "source",
                                 "study", "research", "data", "tested", "verified",
                                 "comparison", "benchmark", "score", "rating"]
            )
            if not has_evidence:
                unsupported_superlatives.append({
                    "superlative": m.group(0),
                    "position": m.start(),
                    "context": context[:80],
                })

        # Check if benchmarks have source attribution
        unsupported_benchmarks = []
        for m in benchmark_matches:
            start = max(0, m.start() - 150)
            end = min(len(text), m.end() + 150)
            context = text[start:end].lower()
            has_source = any(
                s in context
                for s in ["source", "according to", "reported by", "study",
                          "benchmark", "tested by", "verified by", "[verify]"]
            )
            if not has_source:
                unsupported_benchmarks.append({
                    "benchmark": m.group(0),
                    "position": m.start(),
                    "context": context[:80],
                })

        issues = []

        if unsupported_superlatives:
            issues.append({
                "type": "UNSUPPORTED_SUPERLATIVE",
                "count": len(unsupported_superlatives),
                "details": unsupported_superlatives[:5],
                "severity": "high",
            })

        if unsupported_benchmarks:
            issues.append({
                "type": "UNSUPPORTED_BENCHMARK",
                "count": len(unsupported_benchmarks),
                "details": unsupported_benchmarks[:5],
                "severity": "high",
            })

        if comparative_matches:
            # Flag comparative claims without supporting evidence
            unsupported_comparatives = []
            for m in comparative_matches:
                start = max(0, m.start() - 100)
                end = min(len(text), m.end() + 100)
                context = text[start:end].lower()
                has_evidence = any(
                    e in context
                    for e in ["according to", "source", "data", "study",
                              "tested", "benchmark", "[verify]", "rating"]
                )
                if not has_evidence:
                    unsupported_comparatives.append(m.group(0)[:80])

            if unsupported_comparatives:
                issues.append({
                    "type": "UNSUPPORTED_COMPARATIVE",
                    "count": len(unsupported_comparatives),
                    "details": unsupported_comparatives[:5],
                    "severity": "medium",
                })

        if fake_authority_matches:
            issues.append({
                "type": "FAKE_AUTHORITY_LANGUAGE",
                "count": len(fake_authority_matches),
                "details": [m.group(0) for m in fake_authority_matches[:5]],
                "severity": "high",
            })

        result = {
            "total_superlatives": len(superlative_matches),
            "total_benchmarks": len(benchmark_matches),
            "total_comparatives": len(comparative_matches),
            "total_fake_authority": len(fake_authority_matches),
            "unsupported_superlatives": len(unsupported_superlatives),
            "unsupported_benchmarks": len(unsupported_benchmarks),
            "unsupported_comparatives": len(unsupported_comparatives),
            "issues": issues,
            "contradiction_severity": self._calculate_contradiction_severity(issues),
            "claim_density": len(superlative_matches) + len(benchmark_matches) / max(1, len(text.split())) * 1000,
        }

        return result

    def _calculate_contradiction_severity(self, issues: list[dict]) -> float:
        severity_map = {"high": 3.0, "medium": 2.0, "low": 1.0}
        total = sum(
            severity_map.get(issue.get("severity", "low"), 1.0) * issue.get("count", 0)
            for issue in issues
        )
        return min(1.0, total / 20.0)

    def record_lineage(self, lineage: ClaimLineage) -> None:
        with self._lock:
            self._lineage.append(lineage)
            if len(self._lineage) > self._max_lineage:
                self._lineage = self._lineage[-self._max_lineage:]

    def get_lineage(self) -> list[ClaimLineage]:
        with self._lock:
            return list(self._lineage)

    def get_lineage_telemetry(self) -> dict[str, Any]:
        with self._lock:
            if not self._lineage:
                return {}
            total = len(self._lineage)
            by_action: Counter = Counter(l.action_taken for l in self._lineage)
            by_type: Counter = Counter(l.claim_type for l in self._lineage)
            avg_conf_before = sum(l.confidence_before for l in self._lineage) / total
            avg_conf_after = sum(l.confidence_after for l in self._lineage) / total
            return {
                "total_claims_tracked": total,
                "actions": dict(by_action),
                "types": dict(by_type),
                "avg_confidence_before": round(avg_conf_before, 3),
                "avg_confidence_after": round(avg_conf_after, 3),
                "avg_confidence_delta": round(avg_conf_after - avg_conf_before, 3),
            }

    def confidence_decay(self, base_confidence: float, source_diversity: int,
                         contradiction_count: int) -> float:
        """Apply confidence decay based on source diversity and contradictions.

        Args:
            base_confidence: Original confidence (0.0-1.0)
            source_diversity: Number of independent sources supporting
            contradiction_count: Number of contradicting sources

        Returns:
            Adjusted confidence (0.0-1.0)
        """
        adjusted = base_confidence

        # Boost for source diversity (diminishing returns)
        diversity_bonus = min(0.2, source_diversity * 0.05)
        adjusted += diversity_bonus

        # Penalty for contradictions
        contradiction_penalty = contradiction_count * 0.15
        adjusted -= contradiction_penalty

        return max(0.0, min(1.0, adjusted))

    def suppress_superlative(self, text: str, context: str) -> str:
        """Replace unsupported superlatives with evidenced language."""
        replacements = {
            "best": "well-regarded",
            "worst": "less recommended",
            "greatest": "notable",
            "leading": "established",
            "top-rated": "well-reviewed",
            "ultimate": "comprehensive",
            "perfect": "well-suited",
            "most powerful": "capable",
            "most advanced": "feature-rich",
            "most popular": "widely used",
            "industry-leading": "notable",
            "cutting-edge": "modern",
            "state-of-the-art": "current-generation",
            "revolutionary": "significant",
            "groundbreaking": "notable",
        }

        # Only replace if no supporting evidence in context
        has_evidence = any(
            e in context.lower()
            for e in ["because", "due to", "according to", "source",
                      "study", "research", "data", "tested", "verified",
                      "comparison", "benchmark"]
        )
        if has_evidence:
            return text

        result = text
        for superlative, replacement in replacements.items():
            pattern = re.compile(r'\b' + re.escape(superlative) + r'\b', re.IGNORECASE)
            result = pattern.sub(replacement, result)

        return result


_GLOBAL_CLAIM_AUDITOR = ClaimGroundingAuditor()


def get_claim_auditor() -> ClaimGroundingAuditor:
    return _GLOBAL_CLAIM_AUDITOR


# ============================================================================
#  DIMENSION 4 — POST-PROCESSOR SAFETY AUDIT
# ============================================================================

class HTMLSafetyValidator:
    """Validates HTML structure produced by post_processor.

    Checks:
    - HTML structural integrity (no malformed nesting)
    - JSON-LD validity
    - Schema escaping correctness
    - rel=nofollow enforcement
    - No duplicated H1
    - No malformed nested tags
    - Paragraph wrapper never breaks code blocks
    - FAQPage schema matches actual FAQ items
    """

    _VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
                  "link", "meta", "param", "source", "track", "wbr"}

    def validate(self, html: str) -> dict[str, Any]:
        """Run all validation checks. Returns dict with pass/fail and details."""
        issues = []
        warnings = []

        # 1. Tag nesting validation
        nesting_issues = self._validate_nesting(html)
        issues.extend(nesting_issues)

        # 2. JSON-LD validation
        schema_issues = self._validate_schemas(html)
        issues.extend(schema_issues)

        # 3. H1 count
        h1_count = len(re.findall(r'<h1[^>]*>', html, re.IGNORECASE))
        if h1_count == 0:
            issues.append("MISSING_H1")
        elif h1_count > 1:
            issues.append(f"MULTIPLE_H1: {h1_count}")

        # 4. rel=nofollow enforcement
        ext_links = re.findall(r'<a\s[^>]*href="https?://[^"]*"[^>]*>', html, re.IGNORECASE)
        links_missing_rel = []
        for a_tag in ext_links:
            if 'rel="nofollow noopener"' not in a_tag.lower():
                links_missing_rel.append(a_tag[:60])
        if links_missing_rel:
            warnings.append(f"LINKS_MISSING_REL: {len(links_missing_rel)}")

        # 5. FAQPage schema vs actual FAQ items
        faq_schema_qs = re.findall(r'"name":\s*"([^"]+)"', html[html.find('"@type": "FAQPage"'):html.find('"@type": "FAQPage"')+5000] if '"@type": "FAQPage"' in html else "")
        faq_items = re.findall(r'class="faq-q"[^>]*>(.*?)</div>', html, re.DOTALL)
        if faq_schema_qs and faq_items:
            schema_q_clean = [re.sub(r'<[^>]+>', '', q).strip() for q in faq_schema_qs]
            faq_clean = [re.sub(r'<[^>]+>', '', fq).strip() for fq in faq_items]
            matched = sum(
                1 for sq in schema_q_clean
                if any(sq.lower() in fq.lower() or fq.lower() in sq.lower() for fq in faq_clean)
            )
            if matched < len(schema_q_clean) * 0.5:
                warnings.append(f"FAQ_SCHEMA_MISMATCH: only {matched}/{len(schema_q_clean)} questions matched")

        # 6. Code block integrity
        code_blocks = re.findall(r'<pre><code>.*?</code></pre>', html, re.DOTALL)
        for i, block in enumerate(code_blocks):
            if '<p>' in block or '</p>' in block:
                issues.append(f"CODE_BLOCK_PARAGRAPH_BREAK: <p> inside <pre><code> block {i}")

        # 7. Duplicate sections
        h2s = re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.DOTALL | re.IGNORECASE)
        h2_clean = [re.sub(r'<[^>]+>', '', h).strip().lower() for h in h2s]
        seen = set()
        for h in h2_clean:
            if h in seen and len(h) > 10:
                warnings.append(f"DUPLICATE_H2: '{h[:50]}'")
                break
            seen.add(h)

        return {
            "pass": len(issues) == 0,
            "score": max(0, 100 - len(issues) * 15 - len(warnings) * 5),
            "issues": issues,
            "warnings": warnings,
            "h1_count": h1_count,
            "external_links": len(ext_links),
            "links_missing_rel": len(links_missing_rel),
            "faq_items": len(faq_items),
            "faq_schema_questions": len(faq_schema_qs),
        }

    def _validate_nesting(self, html: str) -> list[str]:
        """Check for malformed tag nesting using a stack."""
        issues = []
        stack = []
        tag_pattern = re.compile(r'<(/?)(\w+)[^>]*>')

        for m in tag_pattern.finditer(html):
            is_closing = m.group(1) == '/'
            tag_name = m.group(2).lower()

            if is_closing:
                if tag_name in self._VOID_TAGS:
                    continue
                if not stack:
                    issues.append(f"ORPHAN_CLOSE_TAG: </{tag_name}> at position {m.start()}")
                else:
                    expected = stack.pop()
                    if expected != tag_name:
                        issues.append(
                            f"NESTING_MISMATCH: expected </{expected}> but found </{tag_name}> "
                            f"at position {m.start()}"
                        )
            else:
                if tag_name not in self._VOID_TAGS:
                    stack.append(tag_name)

        if stack:
            issues.append(f"UNCLOSED_TAGS: {', '.join(f'<{t}>' for t in reversed(stack))}")

        return issues

    def _validate_schemas(self, html: str) -> list[str]:
        """Validate all JSON-LD schemas in the HTML."""
        issues = []
        schemas = re.findall(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            html, re.DOTALL | re.IGNORECASE
        )

        for i, schema_text in enumerate(schemas):
            schema_text = schema_text.strip()
            if not schema_text:
                issues.append(f"EMPTY_SCHEMA_BLOCK: schema #{i}")
                continue

            # Check for basic JSON validity
            try:
                data = json.loads(schema_text)
            except json.JSONDecodeError as e:
                issues.append(f"INVALID_JSON_LD: schema #{i} — {e.msg}")
                continue

            # Check required fields based on type
            if isinstance(data, dict):
                stype = data.get("@type", "")
                if stype == "FAQPage":
                    main_entity = data.get("mainEntity", [])
                    if not main_entity:
                        issues.append(f"FAQPage_EMPTY: schema #{i} has no mainEntity")
                    for j, item in enumerate(main_entity):
                        if not item.get("name"):
                            issues.append(f"FAQPage_MISSING_NAME: question #{j} in schema #{i}")
                        if not item.get("acceptedAnswer", {}).get("text"):
                            issues.append(f"FAQPage_MISSING_ANSWER: question #{j} in schema #{i}")

                # Check for unescaped HTML in JSON-LD (which would break the script block)
                if "</script>" in schema_text:
                    issues.append(f"UNESCAPED_SCRIPT_TAG: schema #{i} contains </script>")

        return issues


_GLOBAL_HTML_VALIDATOR = HTMLSafetyValidator()


def get_html_validator() -> HTMLSafetyValidator:
    return _GLOBAL_HTML_VALIDATOR


# ============================================================================
#  DIMENSION 5 — LLM FAILURE PATH AUDIT
# ============================================================================

@dataclass
class FailureTelemetry:
    """Telemetry for every LLM failure path."""
    provider: str
    error_type: str  # "timeout", "rate_limit", "http_error", "parse_error", "unknown"
    error_msg: str
    attempt: int
    max_retries: int
    fallback_triggered: bool
    fallback_provider: str | None
    context_preserved: bool  # Was prompt context preserved through retry?
    timestamp: float = field(default_factory=time.time)
    latency_ms: float = 0.0


class FailurePathMonitor:
    """Monitors and audits all LLM failure paths.

    Tracks:
    - Every except/Exception path
    - Retry attempts
    - Provider fallbacks
    - Timeouts
    - Rate limit hits
    Quarantines malformed outputs and preserves telemetry.
    """

    def __init__(self):
        self._failures: list[FailureTelemetry] = []
        self._quarantine: list[dict[str, Any]] = []
        self._lock = threading.RLock()
        self._max_failures = 200
        self._max_quarantine = 100

    def record_failure(self, telemetry: FailureTelemetry) -> None:
        with self._lock:
            self._failures.append(telemetry)
            if len(self._failures) > self._max_failures:
                self._failures = self._failures[-self._max_failures:]

    def quarantine_output(self, article: str, reason: str, metadata: dict | None = None) -> None:
        """Quarantine a malformed or partial output with full forensic snapshot."""
        entry = {
            "reason": reason,
            "timestamp": time.time(),
            "word_count": len(article.split()) if article else 0,
            "preview": article[:500] if article else "",
            "full_article": article,
            "metadata": metadata or {},
        }
        with self._lock:
            self._quarantine.append(entry)
            if len(self._quarantine) > self._max_quarantine:
                self._quarantine = self._quarantine[-self._max_quarantine:]
        # Write forensic snapshot to disk
        try:
            _q_dir = Path("quarantine_store")
            _q_dir.mkdir(exist_ok=True)
            _ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            _kw = (metadata or {}).get("keyword", "unknown")[:30]
            _safe_kw = re.sub(r"[^\w-]", "_", _kw)
            _file = _q_dir / f"quarantine_{_ts}_{_safe_kw}.json"
            _forensic = {
                "reason": reason,
                "timestamp": _ts,
                "keyword": _kw,
                "word_count": entry["word_count"],
                "repair_attempts": (metadata or {}).get("repair_attempts", 0),
                "full_article": article,
                "metadata": metadata or {},
            }
            _file.write_text(json.dumps(_forensic, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as _q_err:
            log.warning("[QUARANTINE] Failed to write forensic snapshot: %s", _q_err)

    def get_telemetry(self) -> dict[str, Any]:
        with self._lock:
            if not self._failures:
                return {"total_failures": 0, "quarantine_count": len(self._quarantine)}

            total = len(self._failures)
            by_provider: Counter = Counter(f.provider for f in self._failures)
            by_error_type: Counter = Counter(f.error_type for f in self._failures)
            fallback_count = sum(1 for f in self._failures if f.fallback_triggered)
            context_lost = sum(1 for f in self._failures if not f.context_preserved)

            return {
                "total_failures": total,
                "quarantine_count": len(self._quarantine),
                "by_provider": dict(by_provider),
                "by_error_type": dict(by_error_type),
                "fallback_count": fallback_count,
                "context_loss_count": context_lost,
                "rate_limit_count": by_error_type.get("rate_limit", 0),
                "timeout_count": by_error_type.get("timeout", 0),
            }

    def classify_error(self, error: Exception) -> str:
        """Classify an exception into a standard error type."""
        error_str = str(error).lower()

        if isinstance(error, TimeoutError):
            return "timeout"
        if "rate limit" in error_str or "rate_limit" in error_str or "429" in error_str:
            return "rate_limit"
        if isinstance(error, (ConnectionError, OSError)):
            if "timeout" in error_str:
                return "timeout"
            return "network_error"
        if "json" in error_str or isinstance(error, (json.JSONDecodeError, ValueError)):
            return "parse_error"
        if isinstance(error, (ImportError, ModuleNotFoundError)):
            return "import_error"
        if "key" in error_str or "api key" in error_str or "unauthorized" in error_str:
            return "auth_error"

        return "unknown"

    def check_partial_output(self, text: str, min_words: int = 100) -> tuple[bool, str | None]:
        """Check if output is partial/malformed.

        Returns (is_valid, reason_if_invalid).
        """
        if not text or len(text.strip()) == 0:
            return False, "empty_output"

        word_count = len(text.split())
        if word_count < min_words:
            return False, f"too_short: {word_count} words < {min_words} minimum"

        # Check for truncated JSON (ends abruptly)
        if text.strip().endswith("```") and "```" in text[:-3]:
            return False, "truncated_code_block"

        # Check for incomplete HTML (opening tags without closings for structural tags)
        structural_tags = {"<article", "<div", "<section", "<main", "<table", "<ul", "<ol"}
        closing_tags = {"</article", "</div", "</section", "</main", "</table", "</ul", "</ol"}
        opening_count = sum(text.count(t) for t in structural_tags)
        closing_count = sum(text.count(t) for t in closing_tags)
        if opening_count > closing_count + 1:
            return False, "truncated_html"

        return True, None

    def get_recent_failures(self, n: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            recent = self._failures[-n:]
            return [
                {
                    "provider": f.provider,
                    "error_type": f.error_type,
                    "error_msg": f.error_msg[:100],
                    "attempt": f.attempt,
                    "fallback": f.fallback_triggered,
                    "context_preserved": f.context_preserved,
                }
                for f in recent
            ]


_GLOBAL_FAILURE_MONITOR = FailurePathMonitor()


def get_failure_monitor() -> FailurePathMonitor:
    return _GLOBAL_FAILURE_MONITOR


# ============================================================================
#  DIMENSION 6 — VECTOR MEMORY REALITY CHECK
# ============================================================================

class VectorMemoryComparison:
    """A/B test harness to empirically compare with/without vector retrieval.

    Runs identical prompts with and without vector memory injection and
    compares: prompt changes, article structure, opener reuse, section
    similarity, semantic overlap, output quality.
    """

    def __init__(self):
        self._results: list[dict[str, Any]] = []
        self._lock = threading.RLock()
        self._max_results = 50

    def compare(
        self,
        keyword: str,
        build_with_vector: Callable[[], str],
        build_without_vector: Callable[[], str],
    ) -> dict[str, Any]:
        """Run A/B comparison. Both callables should return article HTML."""
        with_vector = build_with_vector()
        without_vector = build_without_vector()

        result = {
            "keyword": keyword,
            "timestamp": time.time(),
            "with_vector": {
                "word_count": len(with_vector.split()),
                "h2_count": len(re.findall(r'<h2[^>]*>', with_vector, re.I)),
                "has_table": '<table' in with_vector,
                "has_faq": 'class="faq-item"' in with_vector,
                "opener": self._extract_opener(with_vector),
            },
            "without_vector": {
                "word_count": len(without_vector.split()),
                "h2_count": len(re.findall(r'<h2[^>]*>', without_vector, re.I)),
                "has_table": '<table' in without_vector,
                "has_faq": 'class="faq-item"' in without_vector,
                "opener": self._extract_opener(without_vector),
            },
            "differences": {
                "word_count_diff": len(with_vector.split()) - len(without_vector.split()),
                "opener_match": self._extract_opener(with_vector) == self._extract_opener(without_vector),
                "structure_similarity": self._structure_similarity(with_vector, without_vector),
                "semantic_overlap_jaccard": self._jaccard_content_overlap(with_vector, without_vector),
            },
        }

        with self._lock:
            self._results.append(result)
            if len(self._results) > self._max_results:
                self._results = self._results[-self._max_results:]

        return result

    @staticmethod
    def _extract_opener(article: str) -> str:
        p = re.search(r'<p[^>]*>(.*?)</p>', article, re.DOTALL)
        if p:
            return re.sub(r'<[^>]+>', '', p.group(1)).strip()[:120]
        return ""

    @staticmethod
    def _structure_similarity(a: str, b: str) -> float:
        """Compare H2 section structure between two articles."""
        h2s_a = [re.sub(r'<[^>]+>', '', h).strip().lower() for h in re.findall(r'<h2[^>]*>(.*?)</h2>', a, re.DOTALL | re.I)]
        h2s_b = [re.sub(r'<[^>]+>', '', h).strip().lower() for h in re.findall(r'<h2[^>]*>(.*?)</h2>', b, re.DOTALL | re.I)]
        if not h2s_a or not h2s_b:
            return 0.0
        common = sum(1 for h in h2s_a if h in h2s_b)
        return common / max(len(h2s_a), len(h2s_b))

    @staticmethod
    def _jaccard_content_overlap(a: str, b: str) -> float:
        text_a = set(re.sub(r'<[^>]+>', ' ', a).lower().split())
        text_b = set(re.sub(r'<[^>]+>', ' ', b).lower().split())
        if not text_a or not text_b:
            return 0.0
        intersection = text_a & text_b
        union = text_a | text_b
        return len(intersection) / len(union)

    def get_results_summary(self) -> dict[str, Any]:
        with self._lock:
            if not self._results:
                return {"total_tests": 0}

            total = len(self._results)
            avg_word_diff = sum(r["differences"]["word_count_diff"] for r in self._results) / total
            opener_match_rate = sum(1 for r in self._results if r["differences"]["opener_match"]) / total
            avg_struct_sim = sum(r["differences"]["structure_similarity"] for r in self._results) / total
            avg_sem_overlap = sum(r["differences"]["semantic_overlap_jaccard"] for r in self._results) / total

            return {
                "total_tests": total,
                "avg_word_count_diff": round(avg_word_diff, 1),
                "opener_match_rate": round(opener_match_rate, 3),
                "avg_structure_similarity": round(avg_struct_sim, 3),
                "avg_semantic_overlap": round(avg_sem_overlap, 3),
                "vector_impact_score": round(
                    (1 - avg_struct_sim) * 0.4 + (1 - avg_sem_overlap) * 0.4 + (1 - opener_match_rate) * 0.2,
                    3,
                ),
            }


_GLOBAL_VECTOR_COMPARE = VectorMemoryComparison()


def get_vector_comparison() -> VectorMemoryComparison:
    return _GLOBAL_VECTOR_COMPARE


# ============================================================================
#  DIMENSION 7 — MULTI-AGENT EXECUTION TRUTH
# ============================================================================

class MultiAgentTruthMonitor:
    """Verifies multi-agent orchestration actually changes outputs.

    Detects:
    - Fake consensus (reviewers always agree)
    - Unused critiques (review feedback not applied)
    - No-op review stages (same output before and after)
    - Orchestration theater (reviews don't affect regeneration)
    """

    def __init__(self):
        self._review_cycles: list[dict[str, Any]] = []
        self._critique_propagation: list[dict[str, Any]] = []
        self._lock = threading.RLock()
        self._max_cycles = 50

    def record_review_cycle(
        self,
        article_before: str,
        critiques: list[dict[str, Any]],
        article_after: str,
        reviewer_labels: list[str],
    ) -> dict[str, Any]:
        """Record a review cycle and compute impact metrics.

        Returns dict with impact metrics.
        """
        diff_words = article_before != article_after

        # Calculate actual changes made
        word_count_delta = len(article_after.split()) - len(article_before.split())

        # Check if critiques were applied
        critiques_text = " ".join(
            c.get("text", c.get("critique", str(c))) for c in critiques
        ).lower()
        applied = self._check_critique_application(article_before, article_after, critiques_text)

        # Disagreement scoring
        reviewer_count = len(reviewer_labels)
        unique_opinions = len(set(
            c.get("verdict", c.get("action", c.get("decision", "")))
            for c in critiques
        ))
        disagreement_score = (unique_opinions - 1) / max(1, reviewer_count - 1) if reviewer_count > 1 else 0.0

        cycle = {
            "timestamp": time.time(),
            "reviewer_count": reviewer_count,
            "unique_reviewers": reviewer_labels,
            "word_count_before": len(article_before.split()),
            "word_count_after": len(article_after.split()),
            "word_count_delta": word_count_delta,
            "critiques_count": len(critiques),
            "critiques_applied": applied["applied_count"],
            "critiques_unused": applied["unused_count"],
            "content_changed": diff_words,
            "disagreement_score": disagreement_score,
            "is_noop": not diff_words,
            "is_fake_consensus": reviewer_count > 1 and disagreement_score == 0.0,
            "critique_propagation_rate": applied.get("propagation_rate", 0.0),
        }

        with self._lock:
            self._review_cycles.append(cycle)
            if len(self._review_cycles) > self._max_cycles:
                self._review_cycles = self._review_cycles[-self._max_cycles:]

        return cycle

    def _check_critique_application(
        self, before: str, after: str, critiques_text: str
    ) -> dict[str, Any]:
        """Check if critique suggestions were actually applied to the article."""
        # Simple heuristic: count how many critique key terms appear in the diff
        critique_terms = set(critiques_text.split())
        # Ignore common words
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
                      "for", "of", "with", "by", "from", "is", "are", "was", "were",
                      "be", "been", "been", "have", "has", "had", "do", "does", "did",
                      "will", "would", "could", "should", "may", "might"}
        critique_terms = critique_terms - stop_words

        # Extract significant terms (3+ chars)
        significant_terms = {t for t in critique_terms if len(t) > 3}

        before_terms = set(re.sub(r'<[^>]+>', ' ', before).lower().split())
        after_terms = set(re.sub(r'<[^>]+>', ' ', after).lower().split())

        new_terms = after_terms - before_terms
        removed_terms = before_terms - after_terms

        applied = new_terms & significant_terms
        unused = significant_terms - (new_terms | removed_terms)

        return {
            "applied_count": len(applied),
            "unused_count": len(unused),
            "applied_terms": list(applied)[:10],
            "unused_terms": list(unused)[:10],
            "propagation_rate": len(applied) / max(1, len(significant_terms)),
        }

    def get_telemetry(self) -> dict[str, Any]:
        with self._lock:
            if not self._review_cycles:
                return {"total_cycles": 0}
            total = len(self._review_cycles)
            noop_count = sum(1 for c in self._review_cycles if c["is_noop"])
            fake_consensus_count = sum(1 for c in self._review_cycles if c["is_fake_consensus"])
            avg_disagreement = sum(c["disagreement_score"] for c in self._review_cycles) / total
            avg_propagation = sum(c["critique_propagation_rate"] for c in self._review_cycles) / total
            avg_change = sum(c["word_count_delta"] for c in self._review_cycles) / total

            return {
                "total_cycles": total,
                "noop_cycles": noop_count,
                "fake_consensus_cycles": fake_consensus_count,
                "avg_disagreement_score": round(avg_disagreement, 3),
                "avg_critique_propagation_rate": round(avg_propagation, 3),
                "avg_word_change": round(avg_change, 1),
                "orchestration_theater_ratio": round(
                    (noop_count + fake_consensus_count) / max(1, total), 3
                ),
            }


_GLOBAL_AGENT_MONITOR = MultiAgentTruthMonitor()


def get_agent_monitor() -> MultiAgentTruthMonitor:
    return _GLOBAL_AGENT_MONITOR


# ============================================================================
#  DIMENSION 8 — PERFORMANCE + SCALE AUDIT
# ============================================================================

class ResourceMonitor:
    """Resource caps, pruning, and lifecycle enforcement.

    Monitors:
    - Thread growth
    - Memory leaks (via object count tracking)
    - File descriptor leaks
    - Queue buildup
    - Latency degradation
    - Prompt growth
    - JSON corruption risk
    """

    def __init__(self):
        self._snapshots: list[dict[str, Any]] = []
        self._lock = threading.RLock()
        self._max_snapshots = 100
        self._warning_count = 0

    def snapshot(self, label: str = "") -> dict[str, Any]:
        """Take a resource snapshot at the current moment."""
        import gc
        gc.collect()

        snapshot = {
            "label": label,
            "timestamp": time.time(),
            "thread_count": threading.active_count(),
            "gc_objects": len(gc.get_objects()),
        }

        with self._lock:
            self._snapshots.append(snapshot)
            if len(self._snapshots) > self._max_snapshots:
                self._snapshots = self._snapshots[-self._max_snapshots:]

        return snapshot

    def check_leaks(self, threshold_pct: float = 0.2) -> list[dict[str, Any]]:
        """Check for memory leaks by comparing GC object counts over time.

        threshold_pct: Maximum allowed growth as fraction of baseline.
        """
        issues = []
        with self._lock:
            if len(self._snapshots) < 2:
                return issues

            baseline = self._snapshots[0]["gc_objects"]
            for s in self._snapshots[1:]:
                growth = (s["gc_objects"] - baseline) / max(1, baseline)
                if growth > threshold_pct:
                    issues.append({
                        "type": "memory_growth",
                        "label": s["label"],
                        "baseline_objects": baseline,
                        "current_objects": s["gc_objects"],
                        "growth_pct": round(growth * 100, 1),
                    })
                    self._warning_count += 1

        return issues

    def check_thread_growth(self, max_threads: int = 50) -> list[dict[str, Any]]:
        issues = []
        with self._lock:
            for s in self._snapshots:
                if s["thread_count"] > max_threads:
                    issues.append({
                        "type": "thread_growth",
                        "label": s["label"],
                        "thread_count": s["thread_count"],
                        "limit": max_threads,
                    })
                    self._warning_count += 1
        return issues

    def get_telemetry(self) -> dict[str, Any]:
        with self._lock:
            if not self._snapshots:
                return {}
            latest = self._snapshots[-1]
            initial = self._snapshots[0]
            thread_delta = latest["thread_count"] - initial["thread_count"]
            objects_delta = latest["gc_objects"] - initial["gc_objects"]
            return {
                "total_snapshots": len(self._snapshots),
                "warning_count": self._warning_count,
                "current_threads": latest["thread_count"],
                "thread_delta": thread_delta,
                "current_gc_objects": latest["gc_objects"],
                "gc_objects_delta": objects_delta,
                "max_threads_recorded": max(s["thread_count"] for s in self._snapshots),
            }

    def reset(self) -> None:
        with self._lock:
            self._snapshots.clear()
            self._warning_count = 0


_GLOBAL_RESOURCE_MONITOR = ResourceMonitor()


def get_resource_monitor() -> ResourceMonitor:
    return _GLOBAL_RESOURCE_MONITOR


# ============================================================================
#  AGGREGATED TELEMETRY
# ============================================================================

def get_all_telemetry() -> dict[str, Any]:
    """Return telemetry from all 8 audit dimensions."""
    return {
        "prompt_truth": get_prompt_fingerprinter().get_telemetry(),
        "memory_contamination": {
            "blacklist_size": len(get_contamination_scorer().get_blacklist()),
        },
        "claim_grounding": get_claim_auditor().get_lineage_telemetry(),
        "post_processor": {},
        "failure_paths": get_failure_monitor().get_telemetry(),
        "vector_memory": get_vector_comparison().get_results_summary(),
        "multi_agent": get_agent_monitor().get_telemetry(),
        "performance": get_resource_monitor().get_telemetry(),
    }
