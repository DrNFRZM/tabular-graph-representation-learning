"""Verify saved metric coverage and README claims without loading models or data.

This is an arithmetic/provenance consistency check, not a retraining result.
It uses no graphmix implementation or machine-learning library.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
HEADLINE_METHODS = (
    "raw",
    "pca",
    "mlp_ae",
    "sage_selfloop",
    "sage_rand",
    "sage_knn",
    "sage_bip",
    "sage_bip_nopool",
    "hgb_ref",
)


def verify(root: Path = ROOT) -> None:
    run = root / "results/full"
    config = yaml.safe_load((run / "config.yaml").read_text(encoding="utf-8"))
    canonical = yaml.safe_load((root / "configs/full.yaml").read_text(encoding="utf-8"))
    if config != canonical:
        raise ValueError("saved and current full configurations differ")
    with (run / "metrics.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    values: dict[tuple[int, str, str], float] = {}
    for row in rows:
        key = (int(row["seed"]), row["method"], row["metric"])
        if key in values:
            raise ValueError(f"duplicate metric key: {key}")
        value = float(row["value"])
        if not math.isfinite(value):
            raise ValueError(f"non-finite metric: {key}")
        values[key] = value
    methods = {method["name"] for method in config["methods"]}
    if config["evaluation"]["hgb_reference"]:
        methods.add("hgb_ref")
    expected = {(int(seed), method) for seed in config["seeds"] for method in methods}
    observed = {(seed, method) for seed, method, metric in values if metric == "probe_auc"}
    if expected != observed:
        raise ValueError("probe AUC method/seed coverage does not match the full configuration")
    if {(seed, method) for seed, method, _ in values} != expected:
        raise ValueError("unexpected method/seed keys in metrics.csv")
    readme = (root / "README.md").read_text(encoding="utf-8")
    for method in HEADLINE_METHODS:
        auc = [values[(seed, method, "probe_auc")] for seed in config["seeds"]]
        cell = f"{statistics.mean(auc):.3f} ± {statistics.stdev(auc):.3f}"
        line = next((line for line in readme.splitlines() if line.startswith(f"| `{method}` |")), "")
        if not line or line.split("|")[2].strip() != cell:
            raise ValueError(f"README AUC table differs from per-seed results: {method}")
    delta = [
        values[(s, "sage_bip", "probe_auc")] - values[(s, "sage_bip_nopool", "probe_auc")]
        for s in config["seeds"]
    ]
    paired = f"{statistics.mean(delta):+.4f} ± {statistics.stdev(delta):.4f}"
    if paired not in readme:
        raise ValueError("README record-value paired difference differs from per-seed results")
    print(
        f"Verified {len(rows)} unique finite metric rows, complete AUC coverage, "
        "nine README rows and the paired control."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    verify(parser.parse_args().root)
