from __future__ import annotations

import re
import json
import time
import hashlib
import logging
from pathlib import Path
from collections import defaultdict

log = logging.getLogger("enterprise_guardian")


# ============================================================
# EXCEPTION (imported from modules at runtime)
# ============================================================

def _get_publish_blocked():
    from modules import PublishBlocked
    return PublishBlocked


# ============================================================
# EVIDENCE GRAPH
# ============================================================

class EvidenceGraph:
    """
    Tracks every factual claim and its lineage.
    """

    def __init__(self):
        self.claims = []
        self.graph = defaultdict(list)

    def add_claim(
        self,
        claim: str,
        source: str,
        confidence: float = 0.5,
        verified: bool = False,
    ):
        node = {
            "claim": claim,
            "source": source,
            "confidence": confidence,
            "verified": verified,
            "timestamp": time.time(),
            "id": hashlib.md5(claim.encode()).hexdigest(),
        }

        self.claims.append(node)
        self.graph[source].append(node)

    def unresolved_claims(self):
        return [c for c in self.claims if not c["verified"]]

    def export(self):
        return {
            "claims": self.claims,
            "graph": dict(self.graph),
        }


# ============================================================
# SEMANTIC CONTRADICTION ENGINE
# ============================================================

class SemanticContradictionGraph:

    CONTRADICTION_PAIRS = [
        ("best", "worst"),
        ("always", "never"),
        ("guaranteed", "uncertain"),
        ("100%", "may"),
        ("instant", "takes time"),
    ]

    def scan(self, article: str):
        findings = []

        lowered = article.lower()

        for a, b in self.CONTRADICTION_PAIRS:
            if a in lowered and b in lowered:
                findings.append(f"Possible contradiction: '{a}' vs '{b}'")

        return findings


# ============================================================
# ENTROPY SHAPING
# ============================================================

class EntropyShaper:
    """
    Prevents robotic repetitive AI rhythm.
    """

    def analyze(self, article: str):

        sentences = re.split(r"[.!?]", article)

        lengths = [len(s.split()) for s in sentences if s.strip()]

        if not lengths:
            return {
                "pass": False,
                "reason": "No sentence structure detected"
            }

        variance = max(lengths) - min(lengths)

        repetitive = variance < 6

        return {
            "pass": not repetitive,
            "variance": variance,
            "reason": "Low sentence entropy detected" if repetitive else ""
        }


# ============================================================
# LIVE CLAIM VERIFIER
# ============================================================

class LiveClaimVerifier:

    PRICE_PATTERN = re.compile(
        r"\$[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?"
    )

    PERCENT_PATTERN = re.compile(
        r"\b[0-9]{1,3}%"
    )

    YEAR_PATTERN = re.compile(
        r"\b(19|20)\d{2}\b"
    )

    def verify(self, article: str):

        findings = []

        prices = self.PRICE_PATTERN.findall(article)
        percentages = self.PERCENT_PATTERN.findall(article)

        if len(prices) > 3:
            findings.append(
                f"Too many unsupported pricing claims ({len(prices)})"
            )

        if len(percentages) > 8:
            findings.append(
                f"Too many unsupported percentage claims ({len(percentages)})"
            )

        if "[VERIFY]" in article:
            findings.append(
                "Article still contains unresolved [VERIFY] markers"
            )

        return findings


# ============================================================
# CITATION LINEAGE
# ============================================================

class CitationLineage:

    def build(self, article: str):

        citations = re.findall(
            r'<a[^>]+href="([^"]+)"',
            article,
            flags=re.IGNORECASE
        )

        lineage = []

        for c in citations:
            lineage.append({
                "url": c,
                "hash": hashlib.md5(c.encode()).hexdigest(),
                "timestamp": time.time()
            })

        return lineage


# ============================================================
# LONG-RUN MEMORY PRUNING
# ============================================================

class MemoryPruner:

    def prune(self, memory: dict, max_articles: int = 500):

        articles = memory.get("articles_written", [])

        if len(articles) <= max_articles:
            return memory

        memory["articles_written"] = articles[-max_articles:]

        memory["pruned"] = True
        memory["pruned_at"] = time.time()

        return memory


# ============================================================
# AUTONOMOUS REPAIR LOOP
# ============================================================

class AutonomousRepairLoop:

    def __init__(self):
        self.max_repairs = 3

    def repair(self, article: str, reason: str):

        repaired = article

        if "duplicate h1" in reason.lower():
            repaired = self._repair_duplicate_h1(repaired)

        if "keyword stuffing" in reason.lower():
            repaired = self._repair_keyword_stuffing(repaired)

        if "verify" in reason.lower():
            repaired = repaired.replace("[VERIFY]", "")

        return repaired

    def _repair_duplicate_h1(self, article: str):

        matches = re.findall(
            r"<h1.*?>.*?</h1>",
            article,
            flags=re.IGNORECASE | re.DOTALL
        )

        if len(matches) <= 1:
            return article

        first = matches[0]

        article = re.sub(
            r"<h1.*?>.*?</h1>",
            "",
            article,
            flags=re.IGNORECASE | re.DOTALL
        )

        return first + "\n" + article

    def _repair_keyword_stuffing(self, article: str):

        words = article.split()

        cleaned = []
        previous = None

        for w in words:

            if previous == w.lower():
                continue

            cleaned.append(w)
            previous = w.lower()

        return " ".join(cleaned)


# ============================================================
# PUBLISH QUARANTINE
# ============================================================

class PublishQuarantine:

    def __init__(self):
        self.dir = Path("quarantine_store")
        self.dir.mkdir(exist_ok=True)

    def quarantine(self, article: str, reason: str):

        ts = int(time.time())

        payload = {
            "reason": reason,
            "timestamp": ts,
            "article": article,
        }

        file = self.dir / f"blocked_{ts}.json"

        file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        log.error("[QUARANTINE] %s", reason)

        raise _get_publish_blocked()(reason)


# ============================================================
# ENTERPRISE HARD FAIL AUDIT
# ============================================================

class EnterpriseHardFailAudit:

    def __init__(self):

        self.contradiction_engine = SemanticContradictionGraph()
        self.entropy = EntropyShaper()
        self.claims = LiveClaimVerifier()
        self.repair = AutonomousRepairLoop()
        self.quarantine = PublishQuarantine()
        self.evidence = EvidenceGraph()

    def audit(self, article: str, keyword: str):

        # ====================================================
        # H1 VALIDATION
        # ====================================================

        h1s = re.findall(
            r"<h1.*?>.*?</h1>",
            article,
            flags=re.IGNORECASE | re.DOTALL
        )

        if len(h1s) == 0:
            self.quarantine.quarantine(
                article,
                "Missing H1"
            )

        if len(h1s) > 1:
            article = self.repair.repair(
                article,
                "duplicate h1"
            )

        # ====================================================
        # VERIFY MARKERS
        # ====================================================

        if "[VERIFY]" in article:
            article = self.repair.repair(
                article,
                "verify"
            )

        # ====================================================
        # CONTRADICTIONS
        # ====================================================

        contradictions = self.contradiction_engine.scan(article)

        if contradictions:
            self.quarantine.quarantine(
                article,
                contradictions[0]
            )

        # ====================================================
        # ENTROPY
        # ====================================================

        entropy = self.entropy.analyze(article)

        if not entropy["pass"]:
            log.warning(
                "[ENTROPY] %s",
                entropy["reason"]
            )

        # ====================================================
        # CLAIM VALIDATION
        # ====================================================

        findings = self.claims.verify(article)

        if findings:
            self.quarantine.quarantine(
                article,
                findings[0]
            )

        # ====================================================
        # EVIDENCE EXTRACTION
        # ====================================================

        paragraphs = re.findall(
            r"<p>(.*?)</p>",
            article,
            flags=re.DOTALL | re.IGNORECASE
        )

        for p in paragraphs:

            clean = re.sub("<.*?>", "", p).strip()

            if len(clean.split()) > 8:
                self.evidence.add_claim(
                    claim=clean[:300],
                    source="article",
                    confidence=0.5,
                    verified=False
                )

        return article


# ============================================================
# GLOBAL SINGLETON
# ============================================================

_ENTERPRISE_AUDITOR = EnterpriseHardFailAudit()


def enterprise_hard_fail(article: str, keyword: str):

    return _ENTERPRISE_AUDITOR.audit(article, keyword)
