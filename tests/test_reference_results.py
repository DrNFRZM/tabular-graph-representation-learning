"""Check that published claims cannot drift from the committed per-seed data."""

import importlib.util
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_results", ROOT / "scripts/verify_results.py")
assert spec is not None and spec.loader is not None
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


@pytest.fixture
def evidence(tmp_path: Path) -> Path:
    for name in ("README.md", "configs/full.yaml", "results/full/config.yaml", "results/full/metrics.csv"):
        dest = tmp_path / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, dest)
    return tmp_path


def test_committed_results_match_claims() -> None:
    verifier.verify(ROOT)


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "readme"])
def test_evidence_corruption_is_detected(evidence: Path, mutation: str) -> None:
    metrics = evidence / "results/full/metrics.csv"
    rows = metrics.read_text(encoding="utf-8").splitlines()
    if mutation == "duplicate":
        metrics.write_text("\n".join([*rows, rows[1]]) + "\n", encoding="utf-8")
    elif mutation == "missing":
        metrics.write_text("\n".join([rows[0], *rows[2:]]) + "\n", encoding="utf-8")
    else:
        readme = evidence / "README.md"
        readme.write_text(
            readme.read_text(encoding="utf-8").replace("0.895 ± 0.002", "0.995 ± 0.002"), encoding="utf-8"
        )
    with pytest.raises(ValueError):
        verifier.verify(evidence)
