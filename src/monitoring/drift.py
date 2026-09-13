"""Drift + performance triggers with 24h per-type debounce."""
from __future__ import annotations

import time
from typing import Any, Dict, Mapping

PSI_HEALTHY = 0.10
PSI_SIGNIFICANT = 0.25
NDCG_DROP_PCT = 0.05
DEBOUNCE_S = 24 * 3600


def _debounced(store: Dict[str, Any], key: str, now: float) -> bool:
    last = float(store.get(key, float("-inf")))
    if now - last < DEBOUNCE_S:
        return True
    store[key] = now
    return False


def check_drift(psi_by_feature: Mapping[str, float], store: Dict[str, Any] | None = None,
                now: float | None = None) -> Dict[str, Any]:
    now = time.time() if now is None else float(now)
    store = {} if store is None else store
    worst = max(psi_by_feature.items(), key=lambda kv: kv[1], default=(None, 0.0))
    feature, psi = worst
    if psi is None or float(psi) <= PSI_SIGNIFICANT:
        band = "healthy" if float(psi or 0) < PSI_HEALTHY else "warning"
        return {"status": band.upper(), "feature": feature, "psi": psi}
    if _debounced(store, "drift", now):
        return {"status": "SUPPRESSED", "feature": feature, "psi": float(psi)}
    return {"status": "RETRAIN RECOMMENDED", "feature": feature,
            "psi": float(psi), "trigger": "drift"}


def check_performance_drop(train_ndcg: float, prod_ndcg: float,
                           store: Dict[str, Any] | None = None,
                           now: float | None = None) -> Dict[str, Any]:
    now = time.time() if now is None else float(now)
    store = {} if store is None else store
    drop = (float(train_ndcg) - float(prod_ndcg)) / max(float(train_ndcg), 1e-9)
    if drop <= NDCG_DROP_PCT:
        return {"status": "HEALTHY", "train_ndcg": train_ndcg, "prod_ndcg": prod_ndcg}
    if _debounced(store, "performance", now):
        return {"status": "SUPPRESSED", "train_ndcg": train_ndcg, "prod_ndcg": prod_ndcg}
    return {"status": "RETRAIN RECOMMENDED", "train_ndcg": float(train_ndcg),
            "prod_ndcg": float(prod_ndcg), "drop_pct": round(drop * 100, 2),
            "trigger": "performance"}
