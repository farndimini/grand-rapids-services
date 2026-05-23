"""
agent_core/state_machine.py — Pipeline State Machine
======================================================
Explicit state tracking for every article generation pipeline:

States:
  PENDING     → Enqueued, not started
  RUNNING     → Actively executing
  FAILED      → Unrecoverable error
  RETRYING    → Backoff retry in progress
  VALIDATING  → Quality gate running
  REWRITING   → Auto-rewrite active
  COMPLETE    → Successfully finished
  CANCELLED   → Cancelled by user/policy

Transitions:
  PENDING → RUNNING
  RUNNING → VALIDATING | FAILED | CANCELLED
  VALIDATING → COMPLETE | REWRITING | FAILED
  REWRITING → VALIDATING | FAILED
  FAILED → RETRYING | FAILED (terminal)
  RETRYING → RUNNING | FAILED

Usage:
    from agent_core.state_machine import PipelineStateMachine, State
    sm = PipelineStateMachine("keyword-123")
    sm.transition(State.RUNNING)
    assert sm.state == State.RUNNING
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any

log = logging.getLogger("agent_core.state_machine")

CHECKPOINT_DIR = Path(__file__).resolve().parent.parent / "checkpoints"


class State(Enum):
    PENDING = auto()
    RUNNING = auto()
    FAILED = auto()
    RETRYING = auto()
    VALIDATING = auto()
    REWRITING = auto()
    COMPLETE = auto()
    CANCELLED = auto()


_STATE_TRANSITIONS: dict[State, set[State]] = {
    State.PENDING: {State.RUNNING, State.CANCELLED},
    State.RUNNING: {State.VALIDATING, State.FAILED, State.CANCELLED},
    State.VALIDATING: {State.COMPLETE, State.REWRITING, State.FAILED},
    State.REWRITING: {State.VALIDATING, State.FAILED},
    State.FAILED: {State.RETRYING, State.FAILED},  # self-loop for terminal
    State.RETRYING: {State.RUNNING, State.FAILED},
    State.COMPLETE: set(),  # terminal
    State.CANCELLED: set(),  # terminal
}


@dataclass
class StateTransition:
    from_state: State
    to_state: State
    timestamp: str
    reason: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


class PipelineStateMachine:
    """Stateful tracker for a single pipeline execution."""

    def __init__(self, pipeline_id: str, keyword: str = ""):
        self.id = pipeline_id
        self.keyword = keyword
        self._state = State.PENDING
        self._history: list[StateTransition] = []
        self._created_at = datetime.now().isoformat()
        self._checkpoint_file = CHECKPOINT_DIR / f"{pipeline_id}.json"
        self._record(State.PENDING, "initialized")

    @property
    def state(self) -> State:
        return self._state

    @property
    def is_terminal(self) -> bool:
        return self._state in (State.COMPLETE, State.FAILED, State.CANCELLED)

    @property
    def is_failed(self) -> bool:
        return self._state == State.FAILED

    def transition(self, new_state: State, reason: str = "", **meta) -> bool:
        """Attempt state transition. Returns True if allowed."""
        if new_state not in _STATE_TRANSITIONS.get(self._state, set()):
            log.warning(
                f"[StateMachine] Illegal transition: {self._state.name} → {new_state.name} "
                f"for {self.id}"
            )
            return False
        old = self._state
        self._state = new_state
        self._record(new_state, reason, **meta)
        log.info(f"[StateMachine] {self.id}: {old.name} → {new_state.name} ({reason})")
        self._checkpoint()
        return True

    def can_transition(self, new_state: State) -> bool:
        return new_state in _STATE_TRANSITIONS.get(self._state, set())

    def _record(self, state: State, reason: str = "", **meta) -> None:
        self._history.append(StateTransition(
            from_state=self._state if self._history else State.PENDING,
            to_state=state,
            timestamp=datetime.now().isoformat(),
            reason=reason,
            meta=meta,
        ))

    def _checkpoint(self) -> None:
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "id": self.id,
            "keyword": self.keyword,
            "state": self._state.name,
            "created_at": self._created_at,
            "updated_at": datetime.now().isoformat(),
            "history": [
                {
                    "from": t.from_state.name,
                    "to": t.to_state.name,
                    "time": t.timestamp,
                    "reason": t.reason,
                    "meta": t.meta,
                }
                for t in self._history
            ],
        }
        try:
            self._checkpoint_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as e:
            log.warning(f"[StateMachine] Checkpoint failed: {e}")

    @classmethod
    def resume(cls, pipeline_id: str) -> PipelineStateMachine | None:
        """Resume a pipeline from checkpoint if it exists."""
        f = CHECKPOINT_DIR / f"{pipeline_id}.json"
        if not f.exists():
            return None
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            sm = cls(pipeline_id, data.get("keyword", ""))
            sm._state = State[data["state"]]
            sm._created_at = data.get("created_at", sm._created_at)
            sm._history = [
                StateTransition(
                    from_state=State[h["from"]],
                    to_state=State[h["to"]],
                    timestamp=h["time"],
                    reason=h["reason"],
                    meta=h.get("meta", {}),
                )
                for h in data.get("history", [])
            ]
            log.info(f"[StateMachine] Resumed {pipeline_id} in state {sm._state.name}")
            return sm
        except (json.JSONDecodeError, KeyError, OSError) as e:
            log.warning(f"[StateMachine] Resume failed for {pipeline_id}: {e}")
            return None

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "keyword": self.keyword,
            "state": self._state.name,
            "terminal": self.is_terminal,
            "failed": self.is_failed,
            "transitions": len(self._history),
            "duration_sec": self._duration_sec(),
        }

    def _duration_sec(self) -> float:
        if len(self._history) < 2:
            return 0.0
        try:
            t0 = datetime.fromisoformat(self._history[0].timestamp)
            t1 = datetime.fromisoformat(self._history[-1].timestamp)
            return (t1 - t0).total_seconds()
        except ValueError:
            return 0.0
