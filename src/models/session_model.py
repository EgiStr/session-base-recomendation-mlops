"""V4 sequential session model — RESERVED INTERFACE ONLY (deferred).

SASRec/GRU4Rec ships in a future cycle. This stub exists so the serving and
training layers can type against a session-model contract without any V4
training/serving code in this cycle.
"""
from __future__ import annotations

from typing import Any


class SessionModelProtocol:
    """Reserved contract for the future V4 sequential model."""

    def fit(self, X: Any, y: Any) -> "SessionModelProtocol":  # pragma: no cover
        raise NotImplementedError("V4 session model deferred — interface reserved only")

    def predict(self, X: Any) -> Any:  # pragma: no cover
        raise NotImplementedError("V4 session model deferred — interface reserved only")
