"""
site_intelligence_graph.py — Site-Wide Knowledge Graph
=======================================================
Persistent graph tracking articles, entities, internal links,
keyword cannibalization, topic overlap, stale content,
citation reuse, trust propagation, and topical authority clusters.

Architecture:
  SiteGraph
    ├── ArticleNode (persistent per-article knowledge)
    ├── EntityNode (extracted named entities)
    ├── TopicCluster (grouped articles by topic)
    ├── AuthorityPropagator (trust flow through graph)
    └── Intelligence operations (cannibalization, gaps, etc.)
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
from collections import defaultdict, Counter

log = logging.getLogger("site_intelligence")

SITE_GRAPH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site_graph_store")


def _ensure_store():
    Path(SITE_GRAPH_DIR).mkdir(parents=True, exist_ok=True)


def _jsonl_append(filename: str, record: dict) -> None:
    _ensure_store()
    path = os.path.join(SITE_GRAPH_DIR, filename)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except OSError as e:
        log.error("Failed to write %s: %s", filename, e)


def _jsonl_read(filename: str) -> list[dict]:
    _ensure_store()
    path = os.path.join(SITE_GRAPH_DIR, filename)
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


def _rewrite(filename: str, records: list[dict]) -> None:
    _ensure_store()
    path = os.path.join(SITE_GRAPH_DIR, filename)
    try:
        with open(path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, default=str) + "\n")
    except OSError as e:
        log.error("Failed to write %s: %s", filename, e)


# ── ArticleNode ──────────────────────────────────────────

class ArticleNode:
    """A single article in the site graph with full metadata."""

    def __init__(
        self,
        keyword: str,
        url: Optional[str] = None,
        title: Optional[str] = None,
        word_count: int = 0,
        niche: str = "default",
        intent: str = "informational",
        quality_score: float = 0.5,
        published_at: Optional[float] = None,
    ):
        self.id = self._make_id(keyword)
        self.keyword = keyword
        self.url = url
        self.title = title or keyword
        self.word_count = word_count
        self.niche = niche
        self.intent = intent
        self.quality_score = max(0.0, min(1.0, quality_score))
        self.published_at = published_at or time.time()
        self.updated_at = self.published_at
        self.entities: list[str] = []
        self.outbound_links: list[str] = []
        self.inbound_links: list[str] = []
        self.citations: list[str] = []
        self.related_article_ids: list[str] = []
        self.topic_cluster_id: Optional[str] = None
        self.trust_score: float = 0.5
        self.is_stale: bool = False

    @staticmethod
    def _make_id(keyword: str) -> str:
        return hashlib.sha256(keyword.strip().lower().encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "keyword": self.keyword,
            "url": self.url,
            "title": self.title,
            "word_count": self.word_count,
            "niche": self.niche,
            "intent": self.intent,
            "quality_score": self.quality_score,
            "published_at": self.published_at,
            "updated_at": self.updated_at,
            "entities": list(self.entities),
            "outbound_links": list(self.outbound_links),
            "inbound_links": list(self.inbound_links),
            "citations": list(self.citations),
            "related_article_ids": list(self.related_article_ids),
            "topic_cluster_id": self.topic_cluster_id,
            "trust_score": self.trust_score,
            "is_stale": self.is_stale,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ArticleNode:
        node = cls(
            keyword=d["keyword"],
            url=d.get("url"),
            title=d.get("title"),
            word_count=d.get("word_count", 0),
            niche=d.get("niche", "default"),
            intent=d.get("intent", "informational"),
            quality_score=d.get("quality_score", 0.5),
            published_at=d.get("published_at"),
        )
        node.id = d["id"]
        node.updated_at = d.get("updated_at", node.published_at)
        node.entities = list(d.get("entities", []))
        node.outbound_links = list(d.get("outbound_links", []))
        node.inbound_links = list(d.get("inbound_links", []))
        node.citations = list(d.get("citations", []))
        node.related_article_ids = list(d.get("related_article_ids", []))
        node.topic_cluster_id = d.get("topic_cluster_id")
        node.trust_score = d.get("trust_score", 0.5)
        node.is_stale = d.get("is_stale", False)
        return node

    def __repr__(self) -> str:
        return f"ArticleNode({self.id[:8]}..., kw={self.keyword})"


# ── EntityNode ───────────────────────────────────────────

class EntityNode:
    """A named entity extracted from articles."""

    def __init__(
        self,
        name: str,
        entity_type: str = "general",
        source_keyword: Optional[str] = None,
    ):
        self.id = self._make_id(name)
        self.name = name
        self.entity_type = entity_type
        self.article_ids: list[str] = []
        self.mention_count: int = 1
        self.first_seen: float = time.time()
        self.last_seen: float = self.first_seen
        self.related_entities: list[str] = []
        self.authority_score: float = 0.3
        if source_keyword:
            self.article_ids.append(source_keyword)

    @staticmethod
    def _make_id(name: str) -> str:
        return hashlib.sha256(name.strip().lower().encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type,
            "article_ids": list(self.article_ids),
            "mention_count": self.mention_count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "related_entities": list(self.related_entities),
            "authority_score": self.authority_score,
        }

    @classmethod
    def from_dict(cls, d: dict) -> EntityNode:
        node = cls(
            name=d["name"],
            entity_type=d.get("entity_type", "general"),
        )
        node.id = d["id"]
        node.article_ids = list(d.get("article_ids", []))
        node.mention_count = d.get("mention_count", 1)
        node.first_seen = d.get("first_seen", time.time())
        node.last_seen = d.get("last_seen", time.time())
        node.related_entities = list(d.get("related_entities", []))
        node.authority_score = d.get("authority_score", 0.3)
        return node


# ── TopicCluster ─────────────────────────────────────────

class TopicCluster:
    """A group of articles covering the same topical area."""

    def __init__(self, name: str, niche: str = "default"):
        self.id = self._make_id(name)
        self.name = name
        self.niche = niche
        self.article_ids: list[str] = []
        self.pillar_id: Optional[str] = None
        self.saturation_score: float = 0.0
        self.authority_flow: float = 0.0
        self.created_at: float = time.time()
        self.updated_at: float = self.created_at

    @staticmethod
    def _make_id(name: str) -> str:
        return hashlib.sha256(name.strip().lower().encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "niche": self.niche,
            "article_ids": list(self.article_ids),
            "pillar_id": self.pillar_id,
            "saturation_score": self.saturation_score,
            "authority_flow": self.authority_flow,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> TopicCluster:
        cluster = cls(
            name=d["name"],
            niche=d.get("niche", "default"),
        )
        cluster.id = d["id"]
        cluster.article_ids = list(d.get("article_ids", []))
        cluster.pillar_id = d.get("pillar_id")
        cluster.saturation_score = d.get("saturation_score", 0.0)
        cluster.authority_flow = d.get("authority_flow", 0.0)
        cluster.created_at = d.get("created_at", time.time())
        cluster.updated_at = d.get("updated_at", time.time())
        return cluster


# ── AuthorityPropagator ──────────────────────────────────

class AuthorityPropagator:
    """Propagates trust/authority through the article graph."""

    def propagate(
        self,
        articles: list[ArticleNode],
        damping: float = 0.85,
        iterations: int = 3,
    ) -> list[ArticleNode]:
        """Simple PageRank-style propagation through link graph."""
        if not articles:
            return articles

        article_map = {a.id: a for a in articles}
        scores = {a.id: a.trust_score for a in articles}

        for _ in range(iterations):
            new_scores = {}
            for a in articles:
                base = scores.get(a.id, 0.5)
                # Incoming link boost
                incoming_boost = 0.0
                incoming_count = 0
                for other in articles:
                    if a.id in other.outbound_links:
                        incoming_boost += scores.get(other.id, 0.5)
                        incoming_count += 1
                if incoming_count > 0:
                    incoming_boost /= incoming_count

                new_scores[a.id] = damping * base + (1 - damping) * incoming_boost

            scores = new_scores

        for a in articles:
            a.trust_score = max(0.0, min(1.0, scores.get(a.id, a.trust_score)))

        return articles


# ── SiteGraph ────────────────────────────────────────────

class SiteGraph:
    """Persistent site-wide knowledge graph.

    Tracks articles, entities, clusters, links, and provides
    intelligence operations like cannibalization detection,
    coverage gap analysis, and internal link suggestions.
    """

    ARTICLES_FILE = "articles.jsonl"
    ENTITIES_FILE = "entities.jsonl"
    CLUSTERS_FILE = "clusters.jsonl"

    def __init__(self):
        self._propagator = AuthorityPropagator()
        _ensure_store()

    # ── Article CRUD ──

    def add_article(self, article: ArticleNode) -> ArticleNode:
        existing = self.get_article(article.id)
        if existing:
            article.updated_at = time.time()
            self._upsert_article(article.to_dict())
            return article
        self._upsert_article(article.to_dict())
        return article

    def get_article(self, article_id: str) -> Optional[ArticleNode]:
        for d in _jsonl_read(self.ARTICLES_FILE):
            if d.get("id") == article_id:
                return ArticleNode.from_dict(d)
        return None

    def get_article_by_keyword(self, keyword: str) -> Optional[ArticleNode]:
        kid = ArticleNode._make_id(keyword)
        return self.get_article(kid)

    def get_all_articles(self) -> list[ArticleNode]:
        return [ArticleNode.from_dict(d) for d in _jsonl_read(self.ARTICLES_FILE)]

    def update_article(self, article_id: str, updates: dict) -> bool:
        records = _jsonl_read(self.ARTICLES_FILE)
        for i, d in enumerate(records):
            if d.get("id") == article_id:
                d.update(updates)
                d["updated_at"] = time.time()
                records[i] = d
                _rewrite(self.ARTICLES_FILE, records)
                return True
        return False

    def remove_article(self, article_id: str) -> bool:
        records = _jsonl_read(self.ARTICLES_FILE)
        filtered = [d for d in records if d.get("id") != article_id]
        if len(filtered) < len(records):
            _rewrite(self.ARTICLES_FILE, filtered)
            return True
        return False

    # ── Entity CRUD ──

    def add_entity(self, entity: EntityNode) -> EntityNode:
        existing = None
        for d in _jsonl_read(self.ENTITIES_FILE):
            if d.get("id") == entity.id:
                existing = EntityNode.from_dict(d)
                break
        if existing:
            entity.last_seen = time.time()
            entity.mention_count = existing.mention_count + 1
            combined_ids = list(set(existing.article_ids + entity.article_ids))
            entity.article_ids = combined_ids
            existing_related = set(existing.related_entities)
            for eid in entity.related_entities:
                existing_related.add(eid)
            entity.related_entities = list(existing_related)
            self._upsert_entity(entity.to_dict())
            return entity
        self._upsert_entity(entity.to_dict())
        return entity

    def get_entity(self, entity_id: str) -> Optional[EntityNode]:
        for d in _jsonl_read(self.ENTITIES_FILE):
            if d.get("id") == entity_id:
                return EntityNode.from_dict(d)
        return None

    def get_all_entities(self) -> list[EntityNode]:
        return [EntityNode.from_dict(d) for d in _jsonl_read(self.ENTITIES_FILE)]

    def search_entities(self, name: str) -> list[EntityNode]:
        lower = name.lower()
        return [
            EntityNode.from_dict(d) for d in _jsonl_read(self.ENTITIES_FILE)
            if lower in d.get("name", "").lower()
        ]

    # ── Topic Cluster CRUD ──

    def add_cluster(self, cluster: TopicCluster) -> TopicCluster:
        existing = None
        for d in _jsonl_read(self.CLUSTERS_FILE):
            if d.get("id") == cluster.id:
                existing = TopicCluster.from_dict(d)
                break
        if existing:
            cluster.updated_at = time.time()
            cluster.article_ids = list(set(existing.article_ids + cluster.article_ids))
            self._upsert_cluster(cluster.to_dict())
            return cluster
        self._upsert_cluster(cluster.to_dict())
        return cluster

    def get_cluster(self, cluster_id: str) -> Optional[TopicCluster]:
        for d in _jsonl_read(self.CLUSTERS_FILE):
            if d.get("id") == cluster_id:
                return TopicCluster.from_dict(d)
        return None

    def get_all_clusters(self) -> list[TopicCluster]:
        return [TopicCluster.from_dict(d) for d in _jsonl_read(self.CLUSTERS_FILE)]

    # ── Intelligence Operations ──

    def detect_cannibalization(self, keyword: str) -> list[dict]:
        """Detect competing articles for the same or similar keyword."""
        articles = self.get_all_articles()
        kw_lower = keyword.lower()
        kw_words = set(kw_lower.split())

        candidates = []
        for a in articles:
            a_words = set(a.keyword.lower().split())
            overlap = kw_words & a_words
            if len(overlap) >= max(1, len(kw_words) * 0.3):
                candidates.append({
                    "article_id": a.id,
                    "keyword": a.keyword,
                    "url": a.url,
                    "word_count": a.word_count,
                    "quality_score": a.quality_score,
                    "overlap_words": list(overlap),
                    "overlap_ratio": len(overlap) / max(1, len(kw_words)),
                })

        candidates.sort(key=lambda x: x["overlap_ratio"], reverse=True)
        return candidates

    def detect_missing_topics(self, niche: str, covered_keywords: list[str]) -> list[str]:
        """Suggest topics not yet covered based on entity gaps."""
        articles = self.get_all_articles()
        niche_articles = [a for a in articles if a.niche == niche]

        covered = set(k.lower() for k in covered_keywords)
        existing_keywords = set(a.keyword.lower() for a in niche_articles)

        missing = []
        for a in niche_articles:
            for entity in a.entities:
                e_lower = entity.lower()
                if e_lower not in covered and e_lower not in existing_keywords:
                    missing.append(entity)

        # Deduplicate and score by frequency
        counter = Counter(m.lower() for m in missing)
        scored = [
            {"topic": topic, "frequency": freq}
            for topic, freq in counter.most_common(20)
        ]
        return [s["topic"] for s in scored if s["frequency"] > 1]

    def suggest_internal_links(self, article_id: str, max_suggestions: int = 5) -> list[dict]:
        """Suggest internal links from one article to others."""
        articles = self.get_all_articles()
        source = self.get_article(article_id)
        if not source:
            return []

        source_words = set(source.keyword.lower().split())
        suggestions = []

        for target in articles:
            if target.id == article_id:
                continue
            if target.id in source.outbound_links:
                continue

            target_words = set(target.keyword.lower().split())
            overlap = source_words & target_words
            if overlap:
                relevance = len(overlap) / max(1, len(source_words))
                if relevance > 0.2:
                    suggestions.append({
                        "from_keyword": source.keyword,
                        "from_id": source.id,
                        "to_keyword": target.keyword,
                        "to_id": target.id,
                        "relevance": round(relevance, 3),
                        "trust_score": target.trust_score,
                        "quality_score": target.quality_score,
                    })

        suggestions.sort(key=lambda x: x["relevance"] * x["trust_score"], reverse=True)
        return suggestions[:max_suggestions]

    def detect_orphan_pages(self) -> list[ArticleNode]:
        """Find articles with no inbound links."""
        articles = self.get_all_articles()
        all_inbound = set()
        for a in articles:
            for link_id in a.outbound_links:
                all_inbound.add(link_id)

        orphans = [a for a in articles if a.id not in all_inbound]
        return orphans

    def detect_semantic_duplicates(self, threshold: float = 0.7) -> list[dict]:
        """Detect articles with high keyword overlap (potential duplicates)."""
        articles = self.get_all_articles()
        duplicates = []

        for i in range(len(articles)):
            for j in range(i + 1, len(articles)):
                a, b = articles[i], articles[j]
                a_words = set(a.keyword.lower().split())
                b_words = set(b.keyword.lower().split())
                if not a_words or not b_words:
                    continue
                intersection = a_words & b_words
                union = a_words | b_words
                jaccard = len(intersection) / len(union)
                if jaccard > threshold:
                    duplicates.append({
                        "article_a": {"id": a.id, "keyword": a.keyword},
                        "article_b": {"id": b.id, "keyword": b.keyword},
                        "similarity": round(jaccard, 3),
                        "recommendation": "merge" if jaccard > 0.85 else "differentiate",
                    })

        return duplicates

    def score_topic_saturation(self, cluster_id: str) -> float:
        """Score how saturated a topic cluster is (0.0 = empty, 1.0 = saturated)."""
        cluster = self.get_cluster(cluster_id)
        if not cluster:
            return 0.0
        articles = [a for a in self.get_all_articles() if a.topic_cluster_id == cluster_id]
        if not articles:
            return 0.0

        total_words = sum(a.word_count for a in articles)
        quality_sum = sum(a.quality_score for a in articles)
        avg_quality = quality_sum / len(articles)

        # Saturation based on word depth and quality
        word_depth = min(1.0, total_words / 50000)  # 50k words = saturated
        quality_factor = avg_quality
        saturation = 0.5 * word_depth + 0.3 * quality_factor + 0.2 * min(1.0, len(articles) / 10)

        return min(1.0, saturation)

    def score_authority_flow(self, article_id: str) -> float:
        """Calculate authority flow into an article from the graph."""
        articles = self.get_all_articles()
        article_map = {a.id: a for a in articles}
        target = article_map.get(article_id)
        if not target:
            return 0.0

        # Inbound link authority
        inbound_authority = 0.0
        inbound_count = 0
        for a in articles:
            if target.id in a.outbound_links:
                inbound_authority += a.trust_score * a.quality_score
                inbound_count += 1

        if inbound_count == 0:
            return target.trust_score * 0.5

        return (inbound_authority / inbound_count + target.trust_score) / 2

    def propagate_authority(self) -> int:
        """Run authority propagation across all articles. Returns count updated."""
        articles = self.get_all_articles()
        if not articles:
            return 0
        updated = self._propagator.propagate(articles)
        count = 0
        for a in updated:
            original = self.get_article(a.id)
            if original and abs(a.trust_score - original.trust_score) > 0.01:
                self._upsert_article(a.to_dict())
                count += 1
        return count

    def get_entity_coverage(self) -> dict:
        """Get entity coverage statistics."""
        entities = self.get_all_entities()
        articles = self.get_all_articles()

        type_counts = Counter(e.entity_type for e in entities)
        top_entities = sorted(entities, key=lambda e: e.mention_count, reverse=True)[:10]

        return {
            "total_entities": len(entities),
            "total_articles": len(articles),
            "by_type": dict(type_counts),
            "top_entities": [
                {"name": e.name, "mentions": e.mention_count, "type": e.entity_type}
                for e in top_entities
            ],
        }

    def get_stats(self) -> dict:
        """Get comprehensive site graph statistics."""
        articles = self.get_all_articles()
        entities = self.get_all_entities()
        clusters = self.get_all_clusters()

        stale = [a for a in articles if a.is_stale]
        orphans = self.detect_orphan_pages()
        total_links = sum(len(a.outbound_links) for a in articles)
        total_words = sum(a.word_count for a in articles)

        return {
            "articles": len(articles),
            "entities": len(entities),
            "clusters": len(clusters),
            "stale_articles": len(stale),
            "orphan_pages": len(orphans),
            "total_internal_links": total_links,
            "total_words": total_words,
            "avg_quality": round(sum(a.quality_score for a in articles) / max(1, len(articles)), 3),
            "avg_trust": round(sum(a.trust_score for a in articles) / max(1, len(articles)), 3),
        }

    # ── Internal persistence ──

    def _upsert_article(self, record: dict) -> None:
        records = _jsonl_read(self.ARTICLES_FILE)
        key = "id"
        exists = False
        for i, r in enumerate(records):
            if r.get(key) == record.get(key):
                records[i] = record
                exists = True
                break
        if not exists:
            records.append(record)
        _rewrite(self.ARTICLES_FILE, records)

    def _upsert_entity(self, record: dict) -> None:
        records = _jsonl_read(self.ENTITIES_FILE)
        key = "id"
        exists = False
        for i, r in enumerate(records):
            if r.get(key) == record.get(key):
                records[i] = record
                exists = True
                break
        if not exists:
            records.append(record)
        _rewrite(self.ENTITIES_FILE, records)

    def _upsert_cluster(self, record: dict) -> None:
        records = _jsonl_read(self.CLUSTERS_FILE)
        key = "id"
        exists = False
        for i, r in enumerate(records):
            if r.get(key) == record.get(key):
                records[i] = record
                exists = True
                break
        if not exists:
            records.append(record)
        _rewrite(self.CLUSTERS_FILE, records)


# ── Convenience: extract entities from article ──────────

_SIMPLE_ENTITY_RX = re.compile(
    r'\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b'
)


def extract_entities(text: str) -> list[str]:
    """Simple entity extraction by capitalized phrases."""
    entities = []
    seen = set()
    for match in _SIMPLE_ENTITY_RX.finditer(text):
        entity = match.group(1).strip()
        if len(entity) > 2 and len(entity.split()) <= 4:
            key = entity.lower()
            if key not in seen:
                seen.add(key)
                entities.append(entity)
    return entities


# ── Global Singleton ─────────────────────────────────────

_GRAPH: Optional[SiteGraph] = None


def get_site_graph() -> SiteGraph:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = SiteGraph()
    return _GRAPH


def reset_site_graph() -> None:
    global _GRAPH
    _GRAPH = None


def ingest_article(
    keyword: str,
    article: str,
    niche: str = "default",
    intent: str = "informational",
    quality_score: float = 0.5,
    url: Optional[str] = None,
) -> ArticleNode:
    """Convenience: extract entities and ingest article into site graph."""
    graph = get_site_graph()
    word_count = len(article.split())

    # Create article node
    node = ArticleNode(
        keyword=keyword,
        url=url,
        word_count=word_count,
        niche=niche,
        intent=intent,
        quality_score=quality_score,
    )

    # Extract entities
    text_no_html = re.sub(r"<[^>]+>", " ", article)
    entities = extract_entities(text_no_html)
    node.entities = entities[:20]

    # Extract outbound links
    links = re.findall(r'<a\s[^>]*href="(https?://[^"]+)"', article, re.I)
    node.outbound_links = links[:20]

    # Extract citations
    citations = re.findall(r'href="https?://[^"]+"', article)
    node.citations = citations[:20]

    graph.add_article(node)

    # Register entities
    for entity_name in entities[:20]:
        entity_type = "product" if any(w in entity_name.lower() for w in
                                        ["pro", "max", "lite", "app", "os", "windows", "mac",
                                         "chrome", "firefox", "android", "ios"]) else "general"
        entity = EntityNode(
            name=entity_name,
            entity_type=entity_type,
            source_keyword=keyword,
        )
        graph.add_entity(entity)

    return node


def suggest_internal_links_for(keyword: str, max_suggestions: int = 5) -> list[dict]:
    """Quick-access: suggest internal links for a keyword."""
    graph = get_site_graph()
    article = graph.get_article_by_keyword(keyword)
    if not article:
        return []
    return graph.suggest_internal_links(article.id, max_suggestions)
