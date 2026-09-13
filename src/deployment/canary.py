"""Step-gated canary ladder + auto-rollback (simulation-grade, deterministic)."""
from __future__ import annotations

LADDER = ["95/5", "75/25", "50/50", "0/100"]
WINDOW = 500
ADVANCE_ERR_MAX = 0.01
ADVANCE_P95_MAX_MS = 100.0
ROLLBACK_ERR = 0.02
ROLLBACK_P95_MS = 200.0


def evaluate_step(current: str, err_rate: float, p95_ms: float,
                  window: int = WINDOW) -> dict:
    err, p95 = float(err_rate), float(p95_ms)
    if err > ROLLBACK_ERR or p95 > ROLLBACK_P95_MS:
        return {"current": current, "next": "100/0", "challenger": "unhealthy",
                "action": "rollback", "window": window}
    if err <= ADVANCE_ERR_MAX and p95 <= ADVANCE_P95_MAX_MS and window >= WINDOW:
        if current in LADDER:
            nxt = LADDER[min(LADDER.index(current) + 1, len(LADDER) - 1)]
            action = "advance" if nxt != current else "hold"
        else:
            nxt, action = current, "hold"
        return {"current": current, "next": nxt, "challenger": "healthy",
                "action": action, "window": window}
    return {"current": current, "next": current, "challenger": "healthy",
            "action": "hold", "window": window}
