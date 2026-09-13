# ML Pipeline

`src/training/train.py` → features → `LGBMRanker` (lambdarank, group sizes) →
`evaluate()` (Recall@K/NDCG@K/MRR@K, means over seeds [42,7,123]) → MLflow
(params, metrics, artifacts, dataset_version, git_commit + dirty flag) →
`ModelRegistry` (HotelRanker, Champion/Challenger aliases) →
`evaluate_gate` (NDCG@10 ≥ champion AND Recall@20 ≥ champion AND P95 ≤ 100ms
AND error ≤ 1%; ties PASS) → canary-eligible or blocked.

Outage: payload queued locally, promotion BLOCKED until logging succeeds.
V1 baselines (popularity/item-sim) must exist per track before any comparison.
V4 SASRec/GRU4Rec: interface reserved (`SessionModelProtocol`), no training.
