"""
agent_core — Enhanced Core Layer for SEO Agent Pro
====================================================
Provides resilience, parallelism, caching, quality validation,
metrics, telemetry, and intelligent fallback WITHOUT modifying
core files (llm_router.py, modules.py, etc.)

Modules:
  relay               → LLM Router wrapper with retry, fallback chain, circuit breaker
  intelligent_fallback→ Multi-factor provider scoring (cost, quality, latency, success rate)
  parallel            → Concurrent execution engine for pipeline stages
  validator           → Semantic quality validation with E-E-A-T scoring + reward signals
  memory_index        → Searchable memory with keyword indexing
  self_heal           → Auto-recovery, circuit breaker, health monitoring
  metrics_collector   → Centralized pipeline metrics and observability
  telemetry           → Automatic stage instrumentation decorators
  health_dashboard    → System-wide health diagnostics reporter
  cache_manager       → Persistent disk cache with TTL, compression, LRU eviction
"""

from .relay import RelayRouter, CachedLLMCall
from .intelligent_fallback import IntelligentFallback
from .parallel import ParallelEngine, TaskGroup
from .validator import SemanticValidator, QualityReport
from .memory_index import MemoryIndex
from .self_heal import CircuitBreaker, HealthMonitor, SelfHeal
from .metrics_collector import MetricsCollector, get_collector
from .telemetry import TelemetryContext, track_stage, track_llm_call
from .health_dashboard import HealthDashboard
from .cache_manager import CacheManager
from .async_runtime import AsyncRuntime, AsyncRelay, AsyncCircuitBreaker, AsyncTokenBucket
from .async_runtime import TaskSupervisor, timeout_envelope, async_timed
from .metrics_store import MetricsStore
from .state_machine import PipelineStateMachine, State
from .execution_graph import ExecutionGraph, TaskNode
from .planner import AgentPlanner, Policy, Plan, PlanStep
from .rl_optimizer import RewardEngine, StrategyEvolution, RewardSignal, compute_reward
from .task_queue import TaskQueue, TaskRecord, TaskState, RetryPolicy, get_task_queue, reset_task_queue
from .distributed import DistributedPipeline, patch_pipeline, unpatch_pipeline
from .vector_memory import VectorMemory, VectorSearchResult, EmbeddingCache, cosine_similarity
from .memory_adapter import (
    MemoryAdapter, MemoryBackend,
    JsonMemoryBackend, VectorMemoryBackend, HybridMemoryBackend,
    ArticleEntry, SearchEntry,
    migrate_json_to_vector, compare_backends,
)
from .prompt_evolution import MutationRecord, PromptVersion, VersionHistory

__all__ = [
    "RelayRouter",
    "CachedLLMCall",
    "IntelligentFallback",
    "ParallelEngine",
    "TaskGroup",
    "SemanticValidator",
    "QualityReport",
    "MemoryIndex",
    "CircuitBreaker",
    "HealthMonitor",
    "SelfHeal",
    "MetricsCollector",
    "get_collector",
    "TelemetryContext",
    "track_stage",
    "track_llm_call",
    "HealthDashboard",
    "CacheManager",
    "AsyncRuntime",
    "AsyncRelay",
    "AsyncCircuitBreaker",
    "AsyncTokenBucket",
    "TaskSupervisor",
    "timeout_envelope",
    "async_timed",
    "MetricsStore",
    "PipelineStateMachine",
    "State",
    "ExecutionGraph",
    "TaskNode",
    "AgentPlanner",
    "Policy",
    "Plan",
    "PlanStep",
    "RewardEngine",
    "StrategyEvolution",
    "RewardSignal",
    "compute_reward",
    "TaskQueue",
    "TaskRecord",
    "TaskState",
    "RetryPolicy",
    "get_task_queue",
    "reset_task_queue",
    "DistributedPipeline",
    "patch_pipeline",
    "unpatch_pipeline",
    "VectorMemory",
    "VectorSearchResult",
    "EmbeddingCache",
    "cosine_similarity",
    "MemoryAdapter",
    "MemoryBackend",
    "JsonMemoryBackend",
    "VectorMemoryBackend",
    "HybridMemoryBackend",
    "ArticleEntry",
    "SearchEntry",
    "migrate_json_to_vector",
    "compare_backends",
    "MutationRecord",
    "PromptVersion",
    "VersionHistory",
]
