"""
memory_adapter.py — Adapter Layer Between JSON Memory and Vector Memory
=========================================================================
Provides a unified interface that preserves the existing JSON memory
system while optionally routing through vector storage.

Backends:
  • JsonMemoryBackend  — wraps existing memory.py (no vector, no deps)
  • VectorMemoryBackend — ChromaDB + sentence-transformers
  • HybridMemoryBackend — writes to both, reads from vector with JSON fallback

Usage:
    from agent_core.memory_adapter import MemoryAdapter, HybridMemoryBackend
    backend = HybridMemoryBackend()
    adapter = MemoryAdapter(backend)
    adapter.record_article("best laptop", "<article>...", "local")
    results = adapter.search("laptop for programming")
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger("agent_core.memory_adapter")


@dataclass
class ArticleEntry:
    keyword: str
    text: str
    model: str
    word_count: int
    quality_score: int
    date: str
    niche: str = ""
    performance_history: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class SearchEntry:
    keyword: str
    text: str
    model: str
    quality_score: int
    date: str
    niche: str
    score: float
    id: str

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "model": self.model,
            "quality_score": self.quality_score,
            "date": self.date,
            "niche": self.niche,
            "score": round(self.score, 4),
            "id": self.id,
        }


def _make_doc_id(keyword: str, timestamp: str = "") -> str:
    raw = f"{keyword}_{timestamp}_{time.time()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


# ── Abstract Backend ───────────────────────────────────────────

class MemoryBackend(ABC):
    """Unified interface for memory storage."""

    @abstractmethod
    def record_article(
        self,
        keyword: str,
        text: str,
        model: str,
        quality_score: int = 0,
        niche: str = "",
        metadata: dict | None = None,
    ) -> str:
        """Store an article. Returns document ID."""
        ...

    @abstractmethod
    def search(
        self,
        query: str,
        top_k: int = 10,
        niche: str = "",
        model: str = "",
        min_quality: int = 0,
    ) -> list[SearchEntry]:
        """Search for similar articles."""
        ...

    @abstractmethod
    def get_by_keyword(self, keyword: str) -> list[SearchEntry]:
        """Get articles by exact keyword match."""
        ...

    @abstractmethod
    def count(self) -> int:
        """Total articles stored."""
        ...

    @abstractmethod
    def stats(self) -> dict:
        """Backend statistics."""
        ...

    @abstractmethod
    def clear(self) -> int:
        """Remove all. Returns count."""
        ...

    def shutdown(self, wait: bool = True) -> None:
        """Release resources. Default no-op; override in subclasses with thread pools."""


# ── JSON Backend (Existing System) ────────────────────────────

class JsonMemoryBackend(MemoryBackend):
    """Wraps the existing memory.py JSON file system."""

    def __init__(self):
        import memory as mem_module
        self._mem_module = mem_module
        self._mem = mem_module.load()

    def record_article(
        self,
        keyword: str,
        text: str,
        model: str,
        quality_score: int = 0,
        niche: str = "",
        metadata: dict | None = None,
    ) -> str:
        self._mem_module.record_article(self._mem, keyword, text, model, quality_score)
        doc_id = _make_doc_id(keyword, datetime.now().isoformat())

        if niche:
            cluster = self._mem.get("clusters", {}).get(keyword)
            if cluster is None:
                from modules import build_cluster
                try:
                    cluster = build_cluster(keyword, niche, model)
                    self._mem_module.record_cluster(self._mem, keyword, cluster)
                except Exception:
                    log.warning("[ADAPTER] build_cluster failed for '%s'", keyword)

        return doc_id

    def search(
        self,
        query: str,
        top_k: int = 10,
        niche: str = "",
        model: str = "",
        min_quality: int = 0,
    ) -> list[SearchEntry]:
        articles = self._mem.get("articles_written", [])
        results = []
        query_lower = query.lower()

        for a in articles:
            kw = a.get("keyword", "").lower()
            if query_lower and query_lower not in kw:
                continue
            if niche and niche.lower() not in kw:
                continue
            if model and a.get("model") != model:
                continue
            if min_quality > 0 and a.get("quality_score", 0) < min_quality:
                continue

            score = 1.0 if kw == query_lower else 0.5  # simple scoring
            results.append(SearchEntry(
                keyword=a.get("keyword", ""),
                text="",
                model=a.get("model", ""),
                quality_score=a.get("quality_score", 0),
                date=a.get("date", ""),
                niche="",
                score=score,
                id=_make_doc_id(a.get("keyword", ""), a.get("date", "")),
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def get_by_keyword(self, keyword: str) -> list[SearchEntry]:
        return self.search(keyword, top_k=100, exact=True)

    def count(self) -> int:
        return len(self._mem.get("articles_written", []))

    def stats(self) -> dict:
        articles = self._mem.get("articles_written", [])
        return {
            "backend": "json",
            "articles": len(articles),
            "clusters": len(self._mem.get("clusters", {})),
            "keywords_done": len(self._mem.get("keywords_done", [])),
            "patterns_learned": len(self._mem.get("successful_patterns", [])),
            "memory_file": str(self._mem_module.MEMORY_PATH),
        }

    def clear(self) -> int:
        count = len(self._mem["articles_written"])
        self._mem["articles_written"] = []
        self._mem["keywords_done"] = []
        self._mem_module.save(self._mem)
        return count


# ── Vector Backend ─────────────────────────────────────────────

class VectorMemoryBackend(MemoryBackend):
    """Uses VectorMemory (ChromaDB + sentence-transformers)."""

    def __init__(
        self,
        collection_name: str = "seo_articles",
        persist_dir: str | Path = "",
        embed_model: str = "all-MiniLM-L6-v2",
    ):
        from agent_core.vector_memory import VectorMemory, DEFAULT_COLLECTION, DEFAULT_VECTOR_DIR
        self._vm = VectorMemory(
            collection_name=collection_name or DEFAULT_COLLECTION,
            persist_dir=persist_dir or DEFAULT_VECTOR_DIR,
            embed_model_name=embed_model,
        )

    @property
    def vector_memory(self):
        return self._vm

    def record_article(
        self,
        keyword: str,
        text: str,
        model: str,
        quality_score: int = 0,
        niche: str = "",
        metadata: dict | None = None,
    ) -> str:
        if metadata is None:
            metadata = {}
        metadata.update({
            "model": model,
            "quality_score": quality_score,
            "niche": niche or metadata.get("niche", ""),
            "stored_at": time.time(),
        })
        doc_id = _make_doc_id(keyword, str(metadata.get("stored_at", "")))
        self._vm.store(doc_id, text, metadata, keyword=keyword)
        return doc_id

    def record_articles_batch(
        self,
        entries: list[ArticleEntry],
    ) -> list[str]:
        """Store multiple articles in one batch (efficient)."""
        items = []
        ids = []
        for entry in entries:
            doc_id = _make_doc_id(entry.keyword, entry.date)
            ids.append(doc_id)
            meta = {
                "model": entry.model,
                "quality_score": entry.quality_score,
                "niche": entry.niche,
                "word_count": entry.word_count,
                "date": entry.date,
            }
            meta.update(entry.metadata)
            items.append((doc_id, entry.text, meta))
        self._vm.store_batch(items)
        return ids

    def search(
        self,
        query: str,
        top_k: int = 10,
        niche: str = "",
        model: str = "",
        min_quality: int = 0,
    ) -> list[SearchEntry]:
        filters = {}
        if niche:
            filters["niche"] = niche
        if model:
            filters["model"] = model
        if min_quality > 0:
            filters["quality_score"] = {"$gte": min_quality}

        raw = self._vm.search(query, top_k=top_k * 2, filter_metadata=filters or None)

        results = []
        for r in raw:
            if r.score < 0.1:
                continue
            results.append(SearchEntry(
                keyword=r.keyword,
                text=r.text[:500],
                model=r.metadata.get("model", ""),
                quality_score=r.metadata.get("quality_score", 0),
                date=str(r.metadata.get("stored_at", "")),
                niche=r.metadata.get("niche", ""),
                score=r.score,
                id=r.id,
            ))

        return results[:top_k]

    def get_by_keyword(self, keyword: str) -> list[SearchEntry]:
        raw = self._vm.search_by_keyword(keyword, top_k=100)
        return [
            SearchEntry(
                keyword=r.keyword,
                text=r.text[:500],
                model=r.metadata.get("model", ""),
                quality_score=r.metadata.get("quality_score", 0),
                date=str(r.metadata.get("stored_at", "")),
                niche=r.metadata.get("niche", ""),
                score=1.0,
                id=r.id,
            )
            for r in raw
        ]

    def count(self) -> int:
        return self._vm.count()

    def stats(self) -> dict:
        s = self._vm.stats()
        return {
            "backend": "vector",
            "articles": s["doc_count"],
            "embedder": s["embedder"],
            "cache_hit_rate": s["cache_hit_rate"],
            "stores": s["stores"],
            "searches": s["searches"],
            "compactions": s["compactions"],
            "mode": s["mode"],
        }

    def clear(self) -> int:
        return self._vm.clear()

    def compact(self, threshold: float = 0.92) -> dict:
        return self._vm.compact(similarity_threshold=threshold)

    def shutdown(self, wait: bool = True) -> None:
        self._vm.shutdown(wait=wait)


# ── Hybrid Backend ─────────────────────────────────────────────

class HybridMemoryBackend(MemoryBackend):
    """Writes to both JSON and vector backends. Reads from vector with JSON fallback."""

    def __init__(
        self,
        json_backend: JsonMemoryBackend | None = None,
        vector_backend: VectorMemoryBackend | None = None,
        primary_read: str = "vector",
    ):
        self._json = json_backend or JsonMemoryBackend()
        self._vector = vector_backend or VectorMemoryBackend()
        self._primary_read = primary_read  # "vector" | "json"

    @property
    def json(self) -> JsonMemoryBackend:
        return self._json

    @property
    def vector(self) -> VectorMemoryBackend:
        return self._vector

    def record_article(
        self,
        keyword: str,
        text: str,
        model: str,
        quality_score: int = 0,
        niche: str = "",
        metadata: dict | None = None,
    ) -> str:
        json_id = self._json.record_article(keyword, text, model, quality_score, niche, metadata)
        vec_id = self._vector.record_article(keyword, text, model, quality_score, niche, metadata)
        log.debug(f"[ADAPTER] Dual-wrote '{keyword}': json={json_id[:8]} vec={vec_id[:8]}")
        return vec_id

    def search(
        self,
        query: str,
        top_k: int = 10,
        niche: str = "",
        model: str = "",
        min_quality: int = 0,
    ) -> list[SearchEntry]:
        if self._primary_read == "vector":
            results = self._vector.search(query, top_k, niche, model, min_quality)
            if not results:
                results = self._json.search(query, top_k, niche, model, min_quality)
            return results
        else:
            return self._json.search(query, top_k, niche, model, min_quality)

    def get_by_keyword(self, keyword: str) -> list[SearchEntry]:
        vec = self._vector.get_by_keyword(keyword)
        if not vec:
            return self._json.get_by_keyword(keyword)
        return vec

    def count(self) -> int:
        return self._vector.count()

    def stats(self) -> dict:
        vs = self._vector.stats()
        js = self._json.stats()
        return {
            "backend": "hybrid",
            "primary_read": self._primary_read,
            "vector": vs,
            "json": js,
            "total_articles": vs.get("articles", 0),
        }

    def clear(self) -> int:
        vc = self._vector.clear()
        jc = self._json.clear()
        return max(vc, jc)

    def compact(self, threshold: float = 0.92) -> dict:
        return self._vector.compact(threshold)

    def shutdown(self, wait: bool = True) -> None:
        self._vector.shutdown(wait=wait)
        self._json.shutdown(wait=wait)


# ── MemoryAdapter ──────────────────────────────────────────────

class MemoryAdapter:
    """High-level adapter that provides a memory.py-compatible API
    while routing through any MemoryBackend.

    Defaults to HybridMemoryBackend for maximum compatibility.
    """

    def __init__(self, backend: MemoryBackend | None = None):
        self._backend = backend or HybridMemoryBackend()

    @property
    def backend(self) -> MemoryBackend:
        return self._backend

    def record_article(
        self,
        keyword: str,
        text: str,
        model: str,
        quality_score: int = 0,
        niche: str = "",
    ) -> str:
        return self._backend.record_article(keyword, text, model, quality_score, niche)

    def search(
        self,
        query: str,
        top_k: int = 10,
        niche: str = "",
        model: str = "",
        min_quality: int = 0,
    ) -> list[SearchEntry]:
        return self._backend.search(query, top_k, niche, model, min_quality)

    def find_similar(
        self,
        keyword: str,
        top_k: int = 5,
        exclude_self: bool = True,
    ) -> list[SearchEntry]:
        results = self._backend.search(keyword, top_k=top_k + 1)
        if exclude_self and results:
            results = [r for r in results if r.keyword.lower() != keyword.lower()]
        return results[:top_k]

    def count(self) -> int:
        return self._backend.count()

    def stats(self) -> dict:
        return self._backend.stats()

    def clear(self) -> int:
        return self._backend.clear()

    def __del__(self) -> None:
        try:
            self._backend.shutdown(wait=False)
        except Exception:
            pass

    def shutdown(self, wait: bool = True) -> None:
        """Release backend resources (vector memory thread pool, etc.)."""
        self._backend.shutdown(wait=wait)


# ── Migration Utility ─────────────────────────────────────────

def migrate_json_to_vector(
    json_backend: JsonMemoryBackend | None = None,
    vector_backend: VectorMemoryBackend | None = None,
    batch_size: int = 50,
    progress_callback: callable = None,
) -> dict:
    """Migrate all articles from JSON memory to vector memory.

    Returns migration stats.
    """
    if json_backend is None:
        json_backend = JsonMemoryBackend()
    if vector_backend is None:
        vector_backend = VectorMemoryBackend()

    mem = json_backend._mem
    articles = mem.get("articles_written", [])
    total = len(articles)
    migrated = 0
    errors = 0

    if progress_callback:
        progress_callback(0, total)

    # Build batches
    entries = []
    for a in articles:
        keyword = a.get("keyword", "")
        text = a.get("text", a.get("article", ""))
        if not text:
            text = f"Article about {keyword}"
        entries.append(ArticleEntry(
            keyword=keyword,
            text=text,
            model=a.get("model", "local"),
            word_count=a.get("word_count", 0),
            quality_score=a.get("quality_score", 0),
            date=a.get("date", ""),
            niche=a.get("niche", ""),
            metadata=a.get("metadata", {}),
        ))

    # Batch migrate
    for i in range(0, len(entries), batch_size):
        batch = entries[i:i + batch_size]
        try:
            vector_backend.record_articles_batch(batch)
            migrated += len(batch)
        except Exception as e:
            log.error(f"[MIGRATE] Batch {i//batch_size + 1} failed: {e}")
            errors += len(batch)

        if progress_callback:
            progress_callback(min(i + batch_size, total), total)

    # Migrate clusters
    cluster_count = 0
    for keyword, cluster_data in mem.get("clusters", {}).items():
        try:
            cluster_text = json.dumps(cluster_data, ensure_ascii=False)
            vector_backend.record_article(
                keyword=f"cluster:{keyword}",
                text=cluster_text,
                model="local",
                metadata={"type": "cluster", "source_keyword": keyword},
            )
            cluster_count += 1
        except Exception as e:
            log.warning(f"[MIGRATE] Cluster '{keyword}' failed: {e}")

    # Migrate patterns
    pattern_count = 0
    for p in mem.get("successful_patterns", []):
        try:
            vector_backend.record_article(
                keyword=f"pattern:{p.get('type', 'unknown')}",
                text=json.dumps(p, ensure_ascii=False),
                model="local",
                quality_score=p.get("success_count", 0) * 10,
                metadata={"type": "pattern", "source": "successful_patterns"},
            )
            pattern_count += 1
        except Exception:
            log.warning("[ADAPTER] Pattern migration failed for cluster '%s'", p.get("cluster_keyword", "?"))

    summary = {
        "total_articles": total,
        "migrated": migrated,
        "errors": errors,
        "clusters_migrated": cluster_count,
        "patterns_migrated": pattern_count,
        "vector_count": vector_backend.count(),
    }

    log.info(f"[MIGRATE] Complete: {summary}")
    return summary


def compare_backends(
    query: str,
    json_backend: JsonMemoryBackend | None = None,
    vector_backend: VectorMemoryBackend | None = None,
    top_k: int = 10,
) -> dict:
    """Compare search results from JSON vs vector backends for the same query.
    Returns overlap statistics and sample results.
    """
    if json_backend is None:
        json_backend = JsonMemoryBackend()
    if vector_backend is None:
        vector_backend = VectorMemoryBackend()

    json_results = json_backend.search(query, top_k=top_k)
    vector_results = vector_backend.search(query, top_k=top_k)

    json_keywords = {r.keyword for r in json_results}
    vector_keywords = {r.keyword for r in vector_results}
    overlap = json_keywords & vector_keywords
    union = json_keywords | vector_keywords

    return {
        "query": query,
        "json_count": len(json_results),
        "vector_count": len(vector_results),
        "overlap_count": len(overlap),
        "union_count": len(union),
        "jaccard_similarity": round(len(overlap) / len(union), 3) if union else 0.0,
        "json_only": sorted(json_keywords - vector_keywords),
        "vector_only": sorted(vector_keywords - json_keywords),
        "json_results": [r.to_dict() for r in json_results[:5]],
        "vector_results": [r.to_dict() for r in vector_results[:5]],
    }


__all__ = [
    "MemoryAdapter",
    "MemoryBackend",
    "JsonMemoryBackend",
    "VectorMemoryBackend",
    "HybridMemoryBackend",
    "ArticleEntry",
    "SearchEntry",
    "migrate_json_to_vector",
    "compare_backends",
]
