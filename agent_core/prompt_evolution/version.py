from __future__ import annotations

import copy
import difflib
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MutationRecord:
    operation: str  # add | remove | replace | rephrase
    location: str
    old_text: str = ""
    new_text: str = ""
    reason: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "location": self.location,
            "old_text_preview": self.old_text[:80],
            "new_text_preview": self.new_text[:80],
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


@dataclass
class PromptVersion:
    prompt_id: str
    version: int
    content: str
    parent_version: int | None = None
    mutations: list[MutationRecord] = field(default_factory=list)
    score: float | None = None
    score_std: float | None = None
    sample_size: int = 0
    promoted_at: float | None = None
    created_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()[:12]

    def delta_pct(self, other: PromptVersion) -> float:
        if not other:
            return 0.0
        diff = difflib.SequenceMatcher(None, other.content, self.content)
        changes = sum(
            b - a for tag, a, b, _, _ in diff.get_opcodes() if tag != "equal"
        )
        total = max(len(other.content), 1)
        return round(changes / total * 100, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "version": self.version,
            "fingerprint": self.fingerprint,
            "content_length": len(self.content),
            "parent_version": self.parent_version,
            "mutations": [m.to_dict() for m in self.mutations],
            "score": self.score,
            "score_std": self.score_std,
            "sample_size": self.sample_size,
            "promoted_at": self.promoted_at,
            "created_at": self.created_at,
            "delta_pct": 0.0,
            "metadata": self.metadata,
        }


class VersionHistory:
    def __init__(self, prompt_id: str):
        self.prompt_id = prompt_id
        self._versions: list[PromptVersion] = []
        self._latest_version: int = 0

    @property
    def latest(self) -> PromptVersion | None:
        return self._versions[-1] if self._versions else None

    @property
    def count(self) -> int:
        return len(self._versions)

    def add(self, content: str, parent_version: int | None = None,
            mutations: list[MutationRecord] | None = None,
            metadata: dict[str, Any] | None = None) -> PromptVersion:
        self._latest_version += 1
        version = PromptVersion(
            prompt_id=self.prompt_id,
            version=self._latest_version,
            content=content,
            parent_version=parent_version,
            mutations=mutations or [],
            created_at=time.time(),
            metadata=metadata or {},
        )
        self._versions.append(version)
        return version

    def get(self, version: int) -> PromptVersion | None:
        for v in self._versions:
            if v.version == version:
                return v
        return None

    def rollback(self, version: int) -> PromptVersion | None:
        target = self.get(version)
        if target is None:
            return None
        if target == self.latest:
            return target
        record = MutationRecord(
            operation="rollback", location="full",
            reason=f"Rollback to version {version}",
            timestamp=time.time(),
        )
        pv = self.add(
            content=target.content,
            parent_version=self._latest_version,
            mutations=[record],
            metadata={"rollback_from": self._latest_version, "rollback_to": version},
        )
        return pv

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "versions": self._latest_version,
            "current_version": self.latest.version if self.latest else 0,
            "history": [v.to_dict() for v in self._versions],
        }
