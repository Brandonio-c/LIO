"""S6 / A22: explicit h16 proxy opt-in through batch/CLI and honest grouped value.

Uses the labelled synthetic fixture library (`lio profiles fixtures`). The
predictive comparison reuses the existing grouped validation (training-only PCA,
held-out groups); with the optional profiles extra absent it must report
unavailable, never a number.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from lio.food_profiles.ablation import (
    grouped_held_out_proxy_ablation,
    proxy_predictive_comparison,
)
from lio.food_profiles.fixtures import build_fixture_library
from lio.food_profiles.metadata import create_dataset
from lio.food_profiles.pipeline import build_feature_batch
from lio.food_profiles.runs import open_run

pytestmark = pytest.mark.unit
HAS_SKLEARN = importlib.util.find_spec("sklearn") is not None


@pytest.fixture(scope="module")
def library(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, object]:
    root = tmp_path_factory.mktemp("profiles")
    info = build_fixture_library(root)
    folders = [root / r for r in info["runs"][:12]]  # foods A/B/C x 2 preps x 2 repeats
    return root, create_dataset(root, folders, synthetic=True)


def _batch(library: tuple[Path, object], proxy: bool):  # type: ignore[no-untyped-def]
    root, ds = library
    return build_feature_batch(root, ds, "amplitude_raw", include_proxy_h16=proxy)  # type: ignore[arg-type]


def _labels(library: tuple[Path, object], batch) -> tuple[list[str], list[dict]]:  # type: ignore[no-untyped-def]
    root, _ds = library
    labels, meta = [], []
    for i, rid in enumerate(batch.run_ids):
        m = open_run(root / rid.split(",")[0]).meta
        labels.append(str(m.get("food_label")))
        meta.append({"preparation_id": batch.preparation_ids[i] or m.get("preparation_id"),
                     "food_label": labels[-1]})  # fmt: skip
    return labels, meta


def test_default_excludes_h16_and_opt_in_uses_proxy_namespace(library: tuple[Path, object]) -> None:
    off = _batch(library, False)
    on = _batch(library, True)
    assert not any(":h16" in f or f.startswith("proxy_unassigned:") for f in off.feature_ids)
    proxy = [f for f in on.feature_ids if f.startswith("proxy_unassigned:")]
    assert proxy and all("1850" not in f.split(":")[0] for f in proxy)
    assert not any(f.startswith("primary1850") for f in on.feature_ids)


def test_descriptive_ablation_is_labelled_descriptive(library: tuple[Path, object]) -> None:
    on = _batch(library, True)
    r = grouped_held_out_proxy_ablation(on)
    if r.metric_full is not None:
        assert "descriptive_within_group" in r.metric_name
    assert any("not predictive" in n for n in r.notes) or r.metric_full is None


def test_predictive_unavailable_without_proxy_or_groups(library: tuple[Path, object]) -> None:
    off = _batch(library, False)
    out = proxy_predictive_comparison(off, ["a"] * off.n_rows, [{}] * off.n_rows)
    assert out["available"] is False and "opt-in" in out["reason"]
    on = _batch(library, True)
    out = proxy_predictive_comparison(on, ["a"] * on.n_rows, [{}] * on.n_rows)
    assert out["available"] is False


@pytest.mark.skipif(HAS_SKLEARN, reason="checks the profiles-extra-absent branch")
def test_predictive_unavailable_without_profiles_extra(library: tuple[Path, object]) -> None:
    on = _batch(library, True)
    labels, meta = _labels(library, on)
    out = proxy_predictive_comparison(on, labels, meta)
    assert out["available"] is False and "no comparable folds" in out["reason"]


@pytest.mark.skipif(not HAS_SKLEARN, reason="needs the optional profiles extra (scikit-learn)")
def test_predictive_comparison_identical_folds(library: tuple[Path, object]) -> None:
    on = _batch(library, True)
    labels, meta = _labels(library, on)
    out = proxy_predictive_comparison(on, labels, meta)
    assert out["available"] is True
    assert len(out["accuracy_full"]) == len(out["accuracy_ablated"]) == out["n_folds"]
    assert np.isfinite(out["mean_difference"])
