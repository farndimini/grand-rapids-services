"""
vector_memory.py — Semantic Vector Memory with ChromaDB
========================================================
Provides:
  • ChromaDB local persistent backend with sentence-transformers
  • Embedding cache (LRU) for hot queries
  • Similarity search with metadata filtering
  • Memory compaction (dedup near-duplicates)
  • Thread-safe sync operations + async-safe wrappers
  • Graceful fallback when chromadb is not installed

Usage:
    from agent_core.vector_memory import VectorMemory
    vm = VectorMemory()
    vm.store("article-1", "Best laptop for programming...", {"keyword": "best laptop"})
    results = vm.search("programming laptop", top_k=5)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("agent_core.vector_memory")

# ── ChromaDB detection ─────────────────────────────────────────

_HAS_CHROMADB = False
_HAS_SENTENCE_TRANSFORMERS = False

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    _HAS_CHROMADB = True
except ImportError:
    chromadb = None

try:
    from sentence_transformers import SentenceTransformer
    _HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    SentenceTransformer = None

# ── Defaults ───────────────────────────────────────────────────

DEFAULT_COLLECTION = "seo_articles"
DEFAULT_EMBED_MODEL = "all-MiniLM-L6-v2"
DEFAULT_VECTOR_DIR = Path(__file__).resolve().parent.parent / "vector_store"
CACHE_MAX_SIZE = 512
COMPACTION_SIMILARITY_THRESHOLD = 0.92


@dataclass
class VectorSearchResult:
    id: str
    keyword: str
    text: str
    metadata: dict[str, Any]
    distance: float
    score: float  # 1.0 = perfect match, 0.0 = worst

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "keyword": self.keyword,
            "metadata": self.metadata,
            "distance": round(self.distance, 4),
            "score": round(self.score, 4),
        }


# ── Embedding Cache ─────────────────────────────────────────────

class EmbeddingCache:
    """Thread-safe LRU cache for computed embeddings."""

    def __init__(self, max_size: int = CACHE_MAX_SIZE):
        self._max_size = max_size
        self._cache: dict[str, list[float]] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()

    def get(self, text: str) -> list[float] | None:
        with self._lock:
            return self._cache.get(text)

    def put(self, text: str, embedding: list[float]) -> None:
        with self._lock:
            if text in self._cache:
                self._order.remove(text)
            elif len(self._cache) >= self._max_size:
                oldest = self._order.pop(0)
                del self._cache[oldest]
            self._cache[text] = embedding
            self._order.append(text)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._order.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    def stats(self) -> dict:
        with self._lock:
            return {"size": len(self._cache), "max_size": self._max_size}


# ── Fallback Embedder (when sentence-transformers not available) ─

class _FallbackEmbedder:
    """Character-n-gram embedding when sentence-transformers is missing.
    
    Produces deterministic 384-dim vectors from text for basic similarity.
    Not semantically meaningful but allows tests and basic operations
    without the heavy dependency.
    """

    DIM = 384

    def encode(self, text: str) -> list[float]:
        vec = [0.0] * self.DIM
        text_bytes = text.encode("utf-8")
        for i, b in enumerate(text_bytes):
            vec[i % self.DIM] += (b / 255.0)
        # Normalise
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


# ── Vector Memory ───────────────────────────────────────────────

class VectorMemory:
    """Semantic memory with ChromaDB persistent backend.
    
    Thread-safe for sync use. For async use, see `async_search`, `async_store`.
    """

    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION,
        persist_dir: str | Path = DEFAULT_VECTOR_DIR,
        embed_model_name: str = DEFAULT_EMBED_MODEL,
        cache_size: int = CACHE_MAX_SIZE,
        auto_persist: bool = True,
    ):
        self._collection_name = collection_name
        self._persist_dir = Path(persist_dir)
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._embed_model_name = embed_model_name
        self._auto_persist = auto_persist

        # Thread safety
        self._lock = threading.RLock()
        self._executor = None  # lazy ThreadPoolExecutor for async wraps

        # Embedding cache
        self._embed_cache = EmbeddingCache(max_size=cache_size)

        # Embedder (lazy-init — model loaded on first use)
        self._embedder = None
        self._embedder_lock = threading.Lock()
        self._fallback_active = False

        # ChromaDB client + collection
        self._client = None
        self._collection = None
        if _HAS_CHROMADB:
            self._init_chromadb()
        else:
            log.warning("[VM] ChromaDB not installed — using in-memory dict fallback")
            self._fallback_store: dict[str, dict] = {}

        # Stats
        self._stats = {
            "stores": 0,
            "searches": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "compactions": 0,
            "errors": 0,
        }
        self._started_at = time.time()

    # ── Initialisation ────────────────────────────────────────

    def _ensure_embedder(self):
        """Lazy-init the embedder on first use."""
        if self._embedder is not None:
            return
        with self._embedder_lock:
            if self._embedder is not None:
                return
            if _HAS_SENTENCE_TRANSFORMERS:
                try:
                    import os as _os
                    # Check if model is cached locally to avoid download hang
                    cache_dir = _os.path.expanduser(
                        _os.path.join("~", ".cache", "huggingface", "hub")
                    )
                    model_slug = self._embed_model_name.replace("/", "--")
                    has_cache = any(model_slug in p for p in (_os.listdir(cache_dir) if _os.path.isdir(cache_dir) else []))
                    if not has_cache:
                        log.info(f"[VM] Model '{self._embed_model_name}' not cached — using fallback embedder")
                        self._embedder = _FallbackEmbedder()
                        self._fallback_active = True
                        return
                    model = SentenceTransformer(self._embed_model_name)
                    log.info(f"[VM] Loaded embedder: {self._embed_model_name}")
                    self._embedder = model
                    self._fallback_active = False
                    return
                except Exception as e:
                    log.warning(f"[VM] Failed to load sentence-transformers: {e} — using fallback")
            self._embedder = _FallbackEmbedder()
            self._fallback_active = True

    def _init_chromadb(self):
        try:
            self._client = chromadb.PersistentClient(
                path=str(self._persist_dir),
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                ),
            )
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            count = self._collection.count()
            log.info(f"[VM] ChromaDB ready ({count} docs) @ {self._persist_dir}")
        except Exception as e:
            log.warning(f"[VM] ChromaDB init failed: {e} — using dict fallback")
            self._client = None
            self._collection = None
            self._fallback_store: dict[str, dict] = {}

    # ── Embedding ─────────────────────────────────────────────

    def _embed(self, text: str) -> list[float]:
        self._ensure_embedder()
        cached = self._embed_cache.get(text)
        if cached is not None:
            with self._lock:
                self._stats["cache_hits"] += 1
            return cached

        with self._lock:
            self._stats["cache_misses"] += 1

        vec = self._embedder.encode(text)
        if isinstance(vec, (list, tuple)):
            vec_list = list(vec)
        else:
            vec_list = vec.tolist()

        self._embed_cache.put(text, vec_list)
        return vec_list

    # ── Store ─────────────────────────────────────────────────

    def store(
        self,
        doc_id: str,
        text: str,
        metadata: dict | None = None,
        keyword: str = "",
    ) -> str:
        """Store a document with embedding. Returns doc_id."""
        if metadata is None:
            metadata = {}
        metadata["keyword"] = keyword or metadata.get("keyword", "")
        metadata["stored_at"] = time.time()

        embedding = self._embed(text)

        with self._lock:
            self._stats["stores"] += 1

            if self._collection is not None:
                try:
                    self._collection.add(
                        ids=[doc_id],
                        embeddings=[embedding],
                        metadatas=[metadata],
                        documents=[text],
                    )
                    return doc_id
                except Exception as e:
                    log.warning(f"[VM] ChromaDB store failed: {e}")
                    self._stats["errors"] += 1

            # Fallback: in-memory dict
            self._fallback_store[doc_id] = {
                "text": text,
                "embedding": embedding,
                "metadata": metadata,
            }
            return doc_id

    def store_batch(
        self,
        items: list[tuple[str, str, dict]],
    ) -> list[str]:
        """Store multiple (doc_id, text, metadata) items in one batch."""
        if not items:
            return []

        ids, texts, metadatas = [], [], []
        for doc_id, text, metadata in items:
            ids.append(doc_id)
            texts.append(text)
            metadata["stored_at"] = time.time()
            metadatas.append(metadata)

        # Compute embeddings
        embeddings = [self._embed(t) for t in texts]

        with self._lock:
            self._stats["stores"] += len(items)

            if self._collection is not None:
                try:
                    self._collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=texts)
                    return ids
                except Exception as e:
                    log.warning(f"[VM] ChromaDB batch store failed: {e}")
                    self._stats["errors"] += 1

            for i, doc_id in enumerate(ids):
                self._fallback_store[doc_id] = {
                    "text": texts[i],
                    "embedding": embeddings[i],
                    "metadata": metadatas[i],
                }
            return ids

    # ── Search ────────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 10,
        filter_metadata: dict | None = None,
        threshold: float = 0.0,
    ) -> list[VectorSearchResult]:
        """Semantic search. Returns results sorted by relevance (highest first)."""
        query_embedding = self._embed(query)

        with self._lock:
            self._stats["searches"] += 1

            if self._collection is not None:
                try:
                    where = self._build_where(filter_metadata) if filter_metadata else None
                    results = self._collection.query(
                        query_embeddings=[query_embedding],
                        n_results=top_k,
                        where=where,
                    )
                    return self._format_results(results)
                except Exception as e:
                    log.warning(f"[VM] ChromaDB search failed: {e}")
                    self._stats["errors"] += 1

            return self._fallback_search(query_embedding, top_k, filter_metadata, threshold)

    def search_by_keyword(
        self,
        keyword: str,
        top_k: int = 10,
        exact: bool = False,
    ) -> list[VectorSearchResult]:
        """Search by keyword metadata field."""
        if exact:
            return self.search("", top_k=top_k, filter_metadata={"keyword": keyword})
        return self.search(keyword, top_k=top_k)

    def _build_where(self, filters: dict) -> dict:
        """Convert simple metadata filters to ChromaDB where clause."""
        if not filters:
            return {}
        conditions = []
        for key, value in filters.items():
            if isinstance(value, (int, float)):
                conditions.append({key: value})
            elif isinstance(value, str):
                conditions.append({key: value})
            elif isinstance(value, dict):
                conditions.append({key: value})
            else:
                conditions.append({key: str(value)})
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def _format_results(self, raw: dict) -> list[VectorSearchResult]:
        """Convert ChromaDB raw results to our format."""
        results = []
        if not raw.get("ids") or not raw["ids"][0]:
            return results

        for i, doc_id in enumerate(raw["ids"][0]):
            metadata = {}
            if raw.get("metadatas") and raw["metadatas"][0]:
                metadata = raw["metadatas"][0][i] or {}
            distance = raw["distances"][0][i] if raw.get("distances") else 0.0
            # ChromaDB returns L2 distances by default with cosine space.
            # Distance 0 = identical, 2 = opposite. Convert to score 0-1.
            score = max(0.0, 1.0 - distance / 2.0)

            results.append(VectorSearchResult(
                id=doc_id,
                keyword=metadata.get("keyword", ""),
                text=raw["documents"][0][i] if raw.get("documents") else "",
                metadata=metadata,
                distance=distance,
                score=score,
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def _fallback_search(
        self,
        query_embedding: list[float],
        top_k: int,
        filter_metadata: dict | None,
        threshold: float,
    ) -> list[VectorSearchResult]:
        """In-memory cosine similarity search (fallback when no ChromaDB)."""
        results = []
        for doc_id, doc in self._fallback_store.items():
            if filter_metadata:
                match = all(doc["metadata"].get(k) == v for k, v in filter_metadata.items())
                if not match:
                    continue

            sim = self._cosine_similarity(query_embedding, doc["embedding"])
            if sim < threshold:
                continue

            results.append(VectorSearchResult(
                id=doc_id,
                keyword=doc["metadata"].get("keyword", ""),
                text=doc["text"],
                metadata=doc["metadata"],
                distance=1.0 - sim,
                score=sim,
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    # ── Delete ────────────────────────────────────────────────

    def delete(self, doc_id: str) -> bool:
        """Delete a document by ID."""
        with self._lock:
            if self._collection is not None:
                try:
                    self._collection.delete(ids=[doc_id])
                    return True
                except Exception as e:
                    log.warning(f"[VM] Delete failed: {e}")
                    self._stats["errors"] += 1
                    return False
            return self._fallback_store.pop(doc_id, None) is not None

    def delete_by_metadata(self, filter_metadata: dict) -> int:
        """Delete all documents matching metadata filter. Returns count."""
        with self._lock:
            count = 0
            if self._collection is not None:
                try:
                    where = self._build_where(filter_metadata)
                    # ChromaDB delete with where clause
                    self._collection.delete(where=where)
                    count = self._collection.count()
                    return count
                except Exception as e:
                    log.warning(f"[VM] Bulk delete failed: {e}")
                    self._stats["errors"] += 1

            # Fallback
            to_delete = [did for did, doc in self._fallback_store.items()
                         if all(doc["metadata"].get(k) == v for k, v in filter_metadata.items())]
            for did in to_delete:
                self._fallback_store.pop(did, None)
            return len(to_delete)

    # ── Compaction ────────────────────────────────────────────

    def compact(self, similarity_threshold: float = COMPACTION_SIMILARITY_THRESHOLD) -> dict:
        """Remove near-duplicate documents. Returns compaction stats."""
        with self._lock:
            self._stats["compactions"] += 1
            removed = 0
            kept = 0

            if self._collection is not None:
                try:
                    all_docs = self._collection.get()
                    ids = all_docs.get("ids", [])
                    if not ids:
                        return {"removed": 0, "kept": 0, "threshold": similarity_threshold}

                    embeddings = all_docs.get("embeddings", [])
                    metadatas = all_docs.get("metadatas", [{}] * len(ids))

                    to_remove = set()
                    for i in range(len(ids)):
                        if ids[i] in to_remove:
                            continue
                        for j in range(i + 1, len(ids)):
                            if ids[j] in to_remove:
                                continue
                            sim = self._cosine_similarity(embeddings[i], embeddings[j])
                            if sim >= similarity_threshold:
                                to_remove.add(ids[j])

                    if to_remove:
                        self._collection.delete(ids=list(to_remove))
                    removed = len(to_remove)
                    kept = len(ids) - removed
                    log.info(f"[VM] Compaction: removed {removed} duplicates, kept {kept}")
                except Exception as e:
                    log.warning(f"[VM] Compaction failed: {e}")
                    self._stats["errors"] += 1
                    return {"removed": 0, "kept": 0, "error": str(e)}

            # Fallback compaction
            else:
                ids = list(self._fallback_store.keys())
                to_remove = set()
                for i in range(len(ids)):
                    if ids[i] in to_remove:
                        continue
                    for j in range(i + 1, len(ids)):
                        if ids[j] in to_remove:
                            continue
                        sim = self._cosine_similarity(
                            self._fallback_store[ids[i]]["embedding"],
                            self._fallback_store[ids[j]]["embedding"],
                        )
                        if sim >= similarity_threshold:
                            to_remove.add(ids[j])
                for did in to_remove:
                    self._fallback_store.pop(did, None)
                removed = len(to_remove)
                kept = len(ids) - removed

            return {"removed": removed, "kept": kept, "threshold": similarity_threshold}

    # ── Count ─────────────────────────────────────────────────

    def count(self) -> int:
        with self._lock:
            if self._collection is not None:
                try:
                    return self._collection.count()
                except Exception:
                    log.debug("[VM] count() query failed, falling back to fallback_store count")
            return len(self._fallback_store)

    # ── Clear ─────────────────────────────────────────────────

    def clear(self) -> int:
        """Remove all documents. Returns count removed."""
        with self._lock:
            count = 0
            if self._collection is not None:
                try:
                    count = self._collection.count()
                    self._client.delete_collection(self._collection_name)
                    self._collection = self._client.get_or_create_collection(
                        name=self._collection_name,
                        metadata={"hnsw:space": "cosine"},
                    )
                except Exception as e:
                    log.warning(f"[VM] Clear failed: {e}")
                    self._stats["errors"] += 1
                    return 0
            else:
                count = len(self._fallback_store)
                self._fallback_store.clear()
            self._embed_cache.clear()
            return count

    # ── Get by ID ─────────────────────────────────────────────

    def get(self, doc_id: str) -> VectorSearchResult | None:
        with self._lock:
            if self._collection is not None:
                try:
                    raw = self._collection.get(ids=[doc_id])
                    if raw and raw.get("ids") and raw["ids"][0]:
                        metadata = raw["metadatas"][0][0] if raw.get("metadatas") else {}
                        return VectorSearchResult(
                            id=doc_id,
                            keyword=metadata.get("keyword", ""),
                            text=raw["documents"][0][0] if raw.get("documents") else "",
                            metadata=metadata,
                            distance=0.0,
                            score=1.0,
                        )
                except Exception:
                    log.debug("[VM] get(%s) query failed, falling back to fallback_store", doc_id)
                return None

            doc = self._fallback_store.get(doc_id)
            if doc is None:
                return None
            return VectorSearchResult(
                id=doc_id,
                keyword=doc["metadata"].get("keyword", ""),
                text=doc["text"],
                metadata=doc["metadata"],
                distance=0.0,
                score=1.0,
            )

    # ── List all ──────────────────────────────────────────────

    def list_all(self, limit: int = 100, offset: int = 0) -> list[VectorSearchResult]:
        with self._lock:
            if self._collection is not None:
                try:
                    raw = self._collection.get(limit=limit, offset=offset)
                    return self._format_results_for_list(raw)
                except Exception:
                    log.debug("[VM] list_all() query failed, falling back to fallback_store")

            ids = list(self._fallback_store.keys())[offset:offset + limit]
            results = []
            for did in ids:
                doc = self._fallback_store[did]
                results.append(VectorSearchResult(
                    id=did,
                    keyword=doc["metadata"].get("keyword", ""),
                    text=doc["text"],
                    metadata=doc["metadata"],
                    distance=0.0,
                    score=1.0,
                ))
            return results

    def _format_results_for_list(self, raw: dict) -> list[VectorSearchResult]:
        results = []
        if not raw.get("ids"):
            return results
        for i, doc_id in enumerate(raw["ids"]):
            metadata = raw["metadatas"][i] if raw.get("metadatas") else {}
            results.append(VectorSearchResult(
                id=doc_id,
                keyword=metadata.get("keyword", ""),
                text=raw["documents"][i] if raw.get("documents") else "",
                metadata=metadata,
                distance=0.0,
                score=1.0,
            ))
        return results

    # ── Async wrappers ────────────────────────────────────────

    async def async_search(
        self,
        query: str,
        top_k: int = 10,
        filter_metadata: dict | None = None,
        threshold: float = 0.0,
    ) -> list[VectorSearchResult]:
        """Async-safe search via thread pool."""
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._get_executor(),
            self.search,
            query, top_k, filter_metadata, threshold,
        )

    async def async_store(
        self,
        doc_id: str,
        text: str,
        metadata: dict | None = None,
        keyword: str = "",
    ) -> str:
        """Async-safe store via thread pool."""
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._get_executor(),
            self.store,
            doc_id, text, metadata, keyword,
        )

    async def async_store_batch(
        self,
        items: list[tuple[str, str, dict]],
    ) -> list[str]:
        """Async-safe batch store."""
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._get_executor(),
            self.store_batch,
            items,
        )

    async def async_compact(self, threshold: float = COMPACTION_SIMILARITY_THRESHOLD) -> dict:
        """Async-safe compaction."""
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._get_executor(), self.compact, threshold)

    async def async_count(self) -> int:
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._get_executor(), self.count)

    def _get_executor(self):
        if self._executor is None:
            import concurrent.futures
            self._executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=2,
                thread_name_prefix="vector_mem_",
            )
        return self._executor

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the internal thread executor, releasing all worker threads."""
        if self._executor is not None:
            self._executor.shutdown(wait=wait)
            self._executor = None

    # ── Stats ─────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        with self._lock:
            uptime = time.time() - self._started_at
            embedder_name = self._embed_model_name
            if self._embedder is None:
                embedder_name += " (uninitialized)"
            elif self._fallback_active:
                embedder_name = "n-gram_fallback"
            return {
                "mode": "chromadb" if self._collection is not None else "fallback_dict",
                "doc_count": self.count(),
                "embedder": embedder_name,
                "embed_cache": self._embed_cache.stats(),
                "stores": self._stats["stores"],
                "searches": self._stats["searches"],
                "compactions": self._stats["compactions"],
                "errors": self._stats["errors"],
                "cache_hit_rate": self._cache_hit_rate(),
                "uptime_seconds": round(uptime, 1),
                "persist_dir": str(self._persist_dir),
            }

    def _cache_hit_rate(self) -> float:
        total = self._stats["cache_hits"] + self._stats["cache_misses"]
        return round(self._stats["cache_hits"] / total, 3) if total else 0.0

    def print_stats(self) -> None:
        s = self.stats()
        from llm_router import c
        print(f"\n{c('bold', 'Vector Memory Stats')}")
        print(f"  Mode:            {s['mode']}")
        print(f"  Documents:       {s['doc_count']}")
        print(f"  Embedder:        {s['embedder']}")
        print(f"  Embed cache:     {s['embed_cache']['size']}/{s['embed_cache']['max_size']}")
        print(f"  Cache hit rate:  {s['cache_hit_rate']:.1%}")
        print(f"  Stores:          {s['stores']}")
        print(f"  Searches:        {s['searches']}")
        print(f"  Compactions:     {s['compactions']}")
        print(f"  Errors:          {s['errors']}")
        print(f"  Persist dir:     {s['persist_dir']}")


# ── Embedding similarity utility ───────────────────────────────

def cosine_similarity(a: list[float], b: list[float]) -> float:
    return VectorMemory._cosine_similarity(a, b)


__all__ = [
    "VectorMemory",
    "VectorSearchResult",
    "EmbeddingCache",
    "cosine_similarity",
    "DEFAULT_COLLECTION",
    "DEFAULT_EMBED_MODEL",
    "COMPACTION_SIMILARITY_THRESHOLD",
]
