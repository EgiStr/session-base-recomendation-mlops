"""Fetch the RetailRocket dataset from HuggingFace (auth-free, ~940MB).

The dataset is NOT committed to git (see .gitignore: data/raw_hf/).
Run once before the cold-start load sequence in docs/runbook.md:

    pip install huggingface_hub
    python scripts/fetch_retailrocket.py [--dest data/raw_hf]

Layout after fetch:
    data/raw_hf/data/RetailRocket-Recommender-Data/data/
        events.csv, item_properties_part1.csv,
        item_properties_part2.csv, category_tree.csv
"""
from __future__ import annotations

import argparse
import os

REPO = "DanielKiani/RetailRocket-Recommender-Data"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default="data/raw_hf")
    args = ap.parse_args()
    from huggingface_hub import snapshot_download

    path = snapshot_download(repo_id=REPO, repo_type="dataset",
                             local_dir=args.dest,
                             allow_patterns=["data/RetailRocket-Recommender-Data/data/*.csv"])
    print(f"DATASET {REPO} -> {os.path.abspath(path)}", flush=True)


if __name__ == "__main__":
    main()
