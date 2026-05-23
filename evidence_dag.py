"""
evidence_dag.py — Evidence Directed Acyclic Graph
==================================================
Claim lineage with full provenance:
  claim
   ├── supporting claims (edges)
   ├── contradicting claims (edges)
   ├── source lineage (url + timestamp)
   ├── verifier lineage (score + name)
   ├── serp consensus (agreement fraction)
   ├── temporal freshness (decay over time)
   └── confidence propagation (through edges)
"""

from __future__ import annotations

import re
import time
import json
import hashlib
import logging
from typing import Any, Optional

log = logging.getLogger("evidence_dag")


# ── Claim Type Constants ──────────────────────────────────

CLAIM_TYPE_PRICE = "price"
CLAIM_TYPE_PERCENTAGE = "percentage"
CLAIM_TYPE_YEAR = "year"
CLAIM_TYPE_SUPERLATIVE = "superlative"
CLAIM_TYPE_COMPARATIVE = "comparative"
CLAIM_TYPE_FACTUAL = "factual"

RELATION_SUPPORTS = "supports"
RELATION_CONTRADICTS = "contradicts"


# ── ClaimNode ─────────────────────────────────────────────

class ClaimNode:
    """A single claim in the evidence DAG with full lineage."""

    def __init__(
        self,
        text: str,
        claim_type: str = CLAIM_TYPE_FACTUAL,
        confidence: float = 0.5,
        source_url: Optional[str] = None,
        extracted_at: Optional[float] = None,
        position: Optional[int] = None,
        metadata: Optional[dict] = None,
    ):
        self.id = self._make_id(text)
        self.text = text
        self.claim_type = claim_type
        self.confidence = max(0.0, min(1.0, confidence))
        self.source_url = source_url
        self.extracted_at = extracted_at or time.time()
        self.verifier_score: Optional[float] = None
        self.verifier_name: Optional[str] = None
        self.serp_consensus: float = 0.0  # 0.0 = no consensus, 1.0 = full
        self.supported_by: list[str] = []
        self.contradicted_by: list[str] = []
        self.position = position  # position in article
        self.metadata = metadata or {}
        self._freshness_decay_rate: float = 0.01  # per day

    @staticmethod
    def _make_id(text: str) -> str:
        raw = text.strip().lower()[:200]
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def temporal_freshness(self, now: Optional[float] = None) -> float:
        """Score 1.0 = just extracted, decay to 0.0 over time."""
        now = now or time.time()
        age_days = (now - self.extracted_at) / 86400
        return max(0.0, 1.0 - age_days * self._freshness_decay_rate)

    def effective_confidence(self, now: Optional[float] = None) -> float:
        """Confidence weighted by temporal freshness and serp consensus."""
        base = self.confidence
        freshness = self.temporal_freshness(now)
        consensus_weight = 0.3 * self.serp_consensus
        verifier_weight = 0.2 * (self.verifier_score or 0.0)
        return max(0.0, min(1.0, 0.5 * base + 0.3 * freshness + consensus_weight + verifier_weight))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "claim_type": self.claim_type,
            "confidence": self.confidence,
            "effective_confidence": self.effective_confidence(),
            "source_url": self.source_url,
            "extracted_at": self.extracted_at,
            "temporal_freshness": self.temporal_freshness(),
            "verifier_score": self.verifier_score,
            "verifier_name": self.verifier_name,
            "serp_consensus": self.serp_consensus,
            "supported_by": list(self.supported_by),
            "contradicted_by": list(self.contradicted_by),
            "position": self.position,
            "metadata": dict(self.metadata),
        }

    def __repr__(self) -> str:
        return f"ClaimNode({self.id}, {self.claim_type}, conf={self.confidence:.2f})"


# ── EvidenceDAG ───────────────────────────────────────────

class EvidenceDAG:
    """Directed Acyclic Graph of claims with full provenance lineage."""

    def __init__(self):
        self.nodes: dict[str, ClaimNode] = {}
        self.edges: list[tuple[str, str, str]] = []  # (from_id, to_id, relation)

    def add_claim(self, claim: ClaimNode) -> ClaimNode:
        existing = self.nodes.get(claim.id)
        if existing:
            # Merge metadata — update confidence if new is higher
            if claim.confidence > existing.confidence:
                existing.confidence = claim.confidence
            if claim.source_url and not existing.source_url:
                existing.source_url = claim.source_url
            if claim.verifier_score is not None:
                existing.verifier_score = claim.verifier_score
            if claim.verifier_name:
                existing.verifier_name = claim.verifier_name
            existing.metadata.update(claim.metadata)
            return existing
        self.nodes[claim.id] = claim
        return claim

    def add_edge(self, from_id: str, to_id: str, relation: str) -> bool:
        """Add a directed edge. Returns False if it creates a cycle."""
        if from_id not in self.nodes or to_id not in self.nodes:
            log.warning("Cannot add edge: node(s) not found")
            return False
        if relation not in (RELATION_SUPPORTS, RELATION_CONTRADICTS):
            log.warning("Unknown relation: %s", relation)
            return False

        # Check for cycles before adding
        temp_edges = self.edges + [(from_id, to_id, relation)]
        if self._would_create_cycle(temp_edges, from_id, to_id):
            log.warning("Edge %s -> %s would create cycle, rejected", from_id, to_id)
            return False

        self.edges.append((from_id, to_id, relation))
        # Supports: forward direction only
        if relation == RELATION_SUPPORTS:
            if from_id not in self.nodes[to_id].supported_by:
                self.nodes[to_id].supported_by.append(from_id)
        # Contradicts: bidirectional (both nodes list each other)
        else:
            for a_id, b_id in [(from_id, to_id), (to_id, from_id)]:
                if a_id not in self.nodes[b_id].contradicted_by:
                    self.nodes[b_id].contradicted_by.append(a_id)
        return True

    def _would_create_cycle(self, edges: list, from_id: str, to_id: str) -> bool:
        """DFS from to_id to see if we can reach from_id."""
        adj: dict[str, list[str]] = {nid: [] for nid in self.nodes}
        for f, t, _r in edges:
            if f in adj:
                adj[f].append(t)
        visited: set[str] = set()
        stack = [to_id]
        while stack:
            node = stack.pop()
            if node == from_id:
                return True
            if node in visited:
                continue
            visited.add(node)
            stack.extend(adj.get(node, []))
        return False

    def get_supporting_chain(self, claim_id: str) -> list[ClaimNode]:
        """Get the full chain of supporting claims (DFS)."""
        if claim_id not in self.nodes:
            return []
        visited: set[str] = set()
        chain: list[ClaimNode] = []
        stack = [claim_id]
        while stack:
            nid = stack.pop()
            if nid in visited:
                continue
            visited.add(nid)
            node = self.nodes.get(nid)
            if node and nid != claim_id:
                chain.append(node)
            if node:
                stack.extend(node.supported_by)
        return chain

    def get_contradictions(self, claim_id: str) -> list[ClaimNode]:
        """Get all claims that contradict a given claim."""
        if claim_id not in self.nodes:
            return []
        results: list[ClaimNode] = []
        for cid in self.nodes[claim_id].contradicted_by:
            if cid in self.nodes:
                results.append(self.nodes[cid])
        # Also find reverse contradictions
        for nid, node in self.nodes.items():
            if claim_id in node.contradicted_by and nid != claim_id:
                results.append(node)
        return results

    def propagate_confidence(self) -> dict[str, float]:
        """Propagate confidence through the graph via support edges.

        A claim's confidence is boosted by supporting claims and
        penalized by contradicting claims.
        """
        updates: dict[str, float] = {}
        for nid, node in self.nodes.items():
            base = node.confidence
            # Boost from supporting claims
            support_boost = 0.0
            for sid in node.supported_by:
                if sid in self.nodes:
                    support_boost += 0.1 * self.nodes[sid].confidence
            support_boost = min(0.3, support_boost)

            # Penalty from contradicting claims
            penalty = 0.0
            for cid in node.contradicted_by:
                if cid in self.nodes:
                    penalty += 0.15 * self.nodes[cid].confidence
            penalty = min(0.4, penalty)

            updated = base + support_boost - penalty
            updates[nid] = max(0.0, min(1.0, updated))
        return updates

    def get_consensus_groups(self, threshold: float = 0.7) -> list[list[ClaimNode]]:
        """Group claims by agreement. Claims that support each other form groups."""
        groups: list[list[ClaimNode]] = []
        assigned: set[str] = set()
        for nid, node in self.nodes.items():
            if nid in assigned:
                continue
            group: list[ClaimNode] = [node]
            assigned.add(nid)
            # Find all claims transitively connected via support edges
            stack = list(node.supported_by)
            while stack:
                sid = stack.pop()
                if sid in assigned or sid not in self.nodes:
                    continue
                assigned.add(sid)
                group.append(self.nodes[sid])
                stack.extend(self.nodes[sid].supported_by)
            if len(group) > 1:
                groups.append(group)
        return groups

    def verify_acyclic(self) -> bool:
        """Verify the entire graph has no cycles."""
        adj: dict[str, list[str]] = {nid: [] for nid in self.nodes}
        for f, t, _r in self.edges:
            adj[f].append(t)
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {nid: WHITE for nid in self.nodes}

        def dfs(nid: str) -> bool:
            color[nid] = GRAY
            for neighbor in adj.get(nid, []):
                if color.get(neighbor) == GRAY:
                    return False  # back edge = cycle
                if color.get(neighbor) == WHITE:
                    if not dfs(neighbor):
                        return False
            color[nid] = BLACK
            return True

        for nid in self.nodes:
            if color[nid] == WHITE:
                if not dfs(nid):
                    return False
        return True

    def claim_count(self) -> int:
        return len(self.nodes)

    def edge_count(self) -> int:
        return len(self.edges)

    def get_claim(self, claim_id: str) -> Optional[ClaimNode]:
        return self.nodes.get(claim_id)

    def to_dict(self) -> dict:
        return {
            "claim_count": self.claim_count(),
            "edge_count": self.edge_count(),
            "is_acyclic": self.verify_acyclic(),
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
            "edges": [{"from": f, "to": t, "relation": r} for f, t, r in self.edges],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


# ── DAGBuilder ────────────────────────────────────────────

class DAGBuilder:
    """Builds an EvidenceDAG from article text by extracting claims."""

    PRICE_RX = re.compile(r"\$[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?")
    PCT_RX = re.compile(r"\b[0-9]{1,3}%")
    YEAR_RX = re.compile(r"\b(19|20)[0-9]{2}\b")
    SUPERLATIVE_RX = re.compile(
        r"\b(best|worst|greatest|largest|smallest|fastest|slowest|"
        r"cheapest|most expensive|highest|lowest|top|leading|ultimate|premier)\b",
        re.I,
    )
    COMPARATIVE_RX = re.compile(
        r"\b(better|worse|faster|slower|cheaper|more expensive|"
        r"higher|lower|greater|less|fewer)\b",
        re.I,
    )

    def build(self, article: str, source_url: Optional[str] = None) -> EvidenceDAG:
        dag = EvidenceDAG()
        sentences = re.split(r"[.!?]+", article)
        offset = 0
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 10:
                offset += 1
                continue

            # Extract prices
            for match in self.PRICE_RX.finditer(sent):
                node = ClaimNode(
                    text=match.group(),
                    claim_type=CLAIM_TYPE_PRICE,
                    source_url=source_url,
                    position=offset,
                    metadata={"sentence": sent[:100]},
                )
                dag.add_claim(node)

            # Extract percentages
            for match in self.PCT_RX.finditer(sent):
                node = ClaimNode(
                    text=match.group(),
                    claim_type=CLAIM_TYPE_PERCENTAGE,
                    source_url=source_url,
                    position=offset,
                    metadata={"sentence": sent[:100]},
                )
                dag.add_claim(node)

            # Extract years
            for match in self.YEAR_RX.finditer(sent):
                node = ClaimNode(
                    text=match.group(),
                    claim_type=CLAIM_TYPE_YEAR,
                    source_url=source_url,
                    position=offset,
                    metadata={"sentence": sent[:100]},
                )
                dag.add_claim(node)

            # Extract superlatives
            for match in self.SUPERLATIVE_RX.finditer(sent):
                node = ClaimNode(
                    text=match.group(),
                    claim_type=CLAIM_TYPE_SUPERLATIVE,
                    source_url=source_url,
                    confidence=0.4,  # lower base confidence for superlatives
                    position=offset,
                    metadata={"sentence": sent[:100]},
                )
                dag.add_claim(node)

            offset += 1
        return dag


# ── DAGVerifier ───────────────────────────────────────────

class DAGVerifier:
    """Verifies claims within the DAG — detects contradictions, propagates confidence."""

    # Pairs that signal contradiction between claims
    CONTRADICTION_PAIRS = [
        ("best", "worst"),
        ("always", "never"),
        ("most", "least"),
        ("highest", "lowest"),
        ("cheapest", "most expensive"),
        ("fastest", "slowest"),
        ("largest", "smallest"),
        ("top", "bottom"),
        ("increase", "decrease"),
        ("more", "less"),
    ]

    def verify(self, dag: EvidenceDAG) -> EvidenceDAG:
        """Run all verification passes on the DAG."""
        self._detect_contradictions(dag)
        self._propagate(dag)
        return dag

    def _detect_contradictions(self, dag: EvidenceDAG) -> None:
        """Scan all node pairs for contradiction signals, add contradiction edges."""
        nodes = list(dag.nodes.values())
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                a, b = nodes[i], nodes[j]
                # Skip same-claim-type pairs that might be complementary
                if a.claim_type == b.claim_type and a.claim_type in (
                    CLAIM_TYPE_PRICE, CLAIM_TYPE_PERCENTAGE, CLAIM_TYPE_YEAR,
                ):
                    continue
                if self._check_contradiction(a, b):
                    dag.add_edge(a.id, b.id, RELATION_CONTRADICTS)

    def _check_contradiction(self, a: ClaimNode, b: ClaimNode) -> bool:
        """Check if two claims contradict each other via known pairs."""
        a_lower = a.text.lower()
        b_lower = b.text.lower()
        for p1, p2 in self.CONTRADICTION_PAIRS:
            if (p1 in a_lower and p2 in b_lower) or (p2 in a_lower and p1 in b_lower):
                return True
        return False

    def _propagate(self, dag: EvidenceDAG) -> None:
        """Apply confidence propagation and update nodes."""
        updates = dag.propagate_confidence()
        for nid, new_conf in updates.items():
            if nid in dag.nodes:
                dag.nodes[nid].confidence = new_conf


# ── DAGConfidencePropagator ───────────────────────────────

class DAGConfidencePropagator:
    """Advanced confidence propagation with iterative refinement."""

    def propagate(
        self,
        dag: EvidenceDAG,
        iterations: int = 3,
        damping: float = 0.85,
    ) -> EvidenceDAG:
        """Iteratively propagate confidence through the DAG.

        Uses a simplified PageRank-style algorithm:
        - Support edges pass confidence forward
        - Contradiction edges dampen confidence
        """
        if dag.claim_count() == 0:
            return dag

        conf: dict[str, float] = {
            nid: node.confidence for nid, node in dag.nodes.items()
        }

        for _ in range(iterations):
            new_conf: dict[str, float] = {}
            for nid, node in dag.nodes.items():
                base = conf.get(nid, node.confidence)

                # Incoming support
                support_sum = 0.0
                for sid in node.supported_by:
                    support_sum += conf.get(sid, 0.5)
                support_avg = support_sum / max(1, len(node.supported_by))

                # Incoming contradiction penalty
                contra_sum = 0.0
                for cid in node.contradicted_by:
                    contra_sum += conf.get(cid, 0.5)
                contra_avg = contra_sum / max(1, len(node.contradicted_by))

                # Damped propagation
                new_val = (
                    damping * base
                    + (1 - damping) * 0.5 * (support_avg - contra_avg + 1)
                )
                new_conf[nid] = max(0.0, min(1.0, new_val))

            conf = new_conf

        for nid, val in conf.items():
            if nid in dag.nodes:
                dag.nodes[nid].confidence = val

        return dag


# ── Global Singleton ──────────────────────────────────────

_DAG_INSTANCE: Optional[EvidenceDAG] = None


def get_global_dag() -> EvidenceDAG:
    global _DAG_INSTANCE
    if _DAG_INSTANCE is None:
        _DAG_INSTANCE = EvidenceDAG()
    return _DAG_INSTANCE


def reset_global_dag() -> None:
    global _DAG_INSTANCE
    _DAG_INSTANCE = None


def build_evidence_dag(
    article: str,
    source_url: Optional[str] = None,
    verify: bool = True,
    propagate: bool = True,
) -> EvidenceDAG:
    """Build, verify, and propagate an Evidence DAG from article text."""
    builder = DAGBuilder()
    dag = builder.build(article, source_url)

    if verify:
        verifier = DAGVerifier()
        verifier.verify(dag)

    if propagate:
        propagator = DAGConfidencePropagator()
        propagator.propagate(dag)

    return dag
