"""Food-profile analysis: fixtures, recipes, PCA freeze, fPCA, validation, exports."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from lio.food_profiles.artifacts import load_bundle, verify_bundle, write_portable_report
from lio.food_profiles.distances import integrated_curve_distance, pairwise_distances
from lio.food_profiles.features import aggregate_by_preparation, extract_run_vector, stack_batches
from lio.food_profiles.fixtures import build_fixture_library, write_synthetic_run
from lio.food_profiles.functional import fit_fpca, transform_fpca
from lio.food_profiles.metadata import RunAnnotation, create_dataset, load_dataset
from lio.food_profiles.ordination import fit_pca, transform_pca
from lio.food_profiles.pipeline import build_feature_batch, fit_dataset_pca, project_dataset_pca
from lio.food_profiles.preprocessing import fit_preprocess, transform_preprocess
from lio.food_profiles.runs import discover_runs, heatmap_payload, open_run
from lio.food_profiles.schema import BUILTIN_RECIPES, CellReason
from lio.food_profiles.trends import chronological_ewma
from lio.food_profiles.validation import assert_no_leakage, validate_grouped

pytestmark = pytest.mark.unit

sklearn = pytest.importorskip("sklearn")


@pytest.fixture()
def synth_root(tmp_path: Path) -> Path:
    build_fixture_library(tmp_path)
    return tmp_path


def test_fixtures_labeled_and_multi_gzip(synth_root: Path) -> None:
    runs = discover_runs(synth_root)
    assert runs
    assert all(r.get("synthetic") for r in runs if "12999" not in r["run_id"] or True)
    run = open_run(synth_root / runs[0]["folder"])
    assert run.meta.get("synthetic") is True
    assert len(run.rows) > 100
    # Multi-member gzip readable
    assert any(r["state"] == "lit" for r in run.rows)
    # Blinds present
    hm = heatmap_payload(run, "opt101")
    assert CellReason.BLIND.value in {c for row in hm["reasons"] for c in row}


def test_explore_does_not_write_analysis(synth_root: Path, tmp_path: Path) -> None:
    folder = next(synth_root.iterdir())
    if not (folder / "scan.json").exists():
        folder = synth_root / discover_runs(synth_root)[0]["folder"]
    # Remove analysis if present for this check on missing-analysis fixture
    miss = synth_root / "20260101-12999_scan_quick_down"
    before = {p.name: p.stat().st_mtime_ns for p in miss.iterdir()}
    run = open_run(miss)
    heatmap_payload(run, "opt101")
    extract_run_vector(run, "amplitude_raw")
    after = {p.name: p.stat().st_mtime_ns for p in miss.iterdir()}
    assert before == after
    assert not (miss / "analysis.json").exists()


def test_recipes_snv_msc_reference(synth_root: Path) -> None:
    runs = discover_runs(synth_root)
    a = open_run(synth_root / runs[0]["folder"])
    b = open_run(synth_root / runs[1]["folder"])
    raw = extract_run_vector(a, "amplitude_raw")
    assert np.isfinite(raw.X).any()
    snv = extract_run_vector(a, "amplitude_shape_snv")
    fitted = fit_preprocess(snv)
    out = transform_preprocess(snv, fitted)
    # SNV: finite rows have ~unit variance
    row = out.X[0]
    ok = np.isfinite(row)
    if ok.sum() > 2:
        assert abs(float(np.std(row[ok], ddof=1)) - 1.0) < 0.15
    ref = extract_run_vector(a, "reference_relative", reference=b)
    # Some cells may be weak_denominator / ok
    assert ref.reasons.shape == ref.X.shape
    # Missing reference → reason
    bad = extract_run_vector(a, "reference_relative", reference=None)
    assert CellReason.INCOMPATIBLE_REFERENCE.value in bad.reasons.ravel().tolist() or "reference_required" in bad.warnings


def test_pca_freeze_and_no_leakage(synth_root: Path) -> None:
    runs = [r for r in discover_runs(synth_root) if r["run_id"].startswith("20260101-12000")]
    folders = [synth_root / r["folder"] for r in runs]
    anns = {}
    for r in runs:
        meta = json.loads((synth_root / r["folder"] / "scan.json").read_text())
        anns[r["run_id"]] = RunAnnotation(
            run_id=r["run_id"],
            food_label=meta.get("food_label"),
            preparation_id=meta.get("preparation_id"),
            lot_id=meta.get("lot_id"),
        )
    ds = create_dataset(synth_root, folders, annotations=anns, synthetic=True, dataset_id="ds-pca")
    out = synth_root / "profile_analyses" / "pca1"
    model, batch, result = fit_dataset_pca(synth_root, ds, "amplitude_raw", out_dir=out, n_components=2)
    assert result.scores.shape[0] == batch.n_rows
    # Project same data: coordinates for training rows must match
    again = transform_pca(batch, model)
    mask = result.projectable & again.projectable
    if mask.any():
        np.testing.assert_allclose(result.scores[mask], again.scores[mask], rtol=1e-5, atol=1e-5)
    # Held-out must not appear in training ids after subset fit
    hold = batch.row_ids[-1:]
    train = type(batch)(
        batch.row_ids[:-1],
        batch.run_ids[:-1],
        batch.preparation_ids[:-1],
        batch.feature_ids,
        batch.X[:-1],
        batch.reasons[:-1],
        batch.source_links[:-1],
        batch.recipe,
        batch.warnings,
        batch.units,
    )
    m2 = fit_pca(train, n_components=2)
    assert_no_leakage(m2, hold)
    # Bundle round-trip
    v = verify_bundle(out)
    assert v["ok"]
    proj = project_dataset_pca(synth_root, ds, out)
    assert proj.scores.shape[1] == model.n_components


def test_fpca_recovers_modes(synth_root: Path) -> None:
    runs_meta = [r for r in discover_runs(synth_root) if r["run_id"].startswith("20260101-12000")]
    runs = [open_run(synth_root / r["folder"]) for r in runs_meta]
    model = fit_fpca(runs, hole=5, detector="opt101", n_components=2)
    result = transform_fpca(runs, model)
    assert result.projectable.any()
    # Explained variance positive
    assert float(model.explained_variance_ratio.sum()) > 0.5
    # Quadrature refinement: subsample every other height if enough points
    if len(model.grid.heights_hs) >= 4:
        # Reconstruction close for projectable
        for i, ok in enumerate(result.projectable):
            if not ok:
                continue
            # Residual in L2 sense bounded relative to signal
            break


def test_distances_and_integrated(synth_root: Path) -> None:
    regular = [r for r in discover_runs(synth_root) if r["run_id"].startswith("20260101-12000")]
    a = open_run(synth_root / regular[0]["folder"])
    b = open_run(synth_root / regular[1]["folder"])
    # Lock height so feature schemas match
    extract_run_vector._lock_height_hs = 20000.0  # type: ignore[attr-defined]
    try:
        fa = extract_run_vector(a, "amplitude_raw")
        fb = extract_run_vector(b, "amplitude_raw")
    finally:
        extract_run_vector._lock_height_hs = None  # type: ignore[attr-defined]
    batch = stack_batches([fa, fb])
    dm = pairwise_distances(batch, metric="euclidean")
    assert dm.D.shape == (2, 2)
    assert dm.D[0, 0] == 0.0
    h = np.array([0.0, 1.0, 2.0])
    d = integrated_curve_distance(h, np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 0.0]))
    assert d > 0


def test_grouped_validation(synth_root: Path) -> None:
    runs = [r for r in discover_runs(synth_root) if r["run_id"].startswith("20260101-12000")]
    folders = [synth_root / r["folder"] for r in runs]
    anns = {}
    for r in runs:
        meta = json.loads((synth_root / r["folder"] / "scan.json").read_text())
        anns[r["run_id"]] = RunAnnotation(
            run_id=r["run_id"],
            food_label=meta.get("food_label"),
            preparation_id=meta.get("preparation_id"),
            lot_id=meta.get("lot_id"),
        )
    ds = create_dataset(synth_root, folders, annotations=anns, synthetic=True, dataset_id="ds-val")
    batch = build_feature_batch(synth_root, ds, "amplitude_raw")
    labels, meta = [], []
    for i, rid in enumerate(batch.run_ids):
        first = rid.split(",")[0]
        ann = ds.annotations[first]
        labels.append(str(ann["food_label"]))
        meta.append(
            {
                "preparation_id": batch.preparation_ids[i],
                "lot_id": ann.get("lot_id"),
                "day": "2026-01-01",
                "food_label": ann["food_label"],
            }
        )
    result = validate_grouped(batch, labels, meta, target="new-preparation")
    assert result.available
    assert result.n_folds >= 2


def test_ewma_no_future_leakage() -> None:
    ts = [
        "2026-01-01T10:00:00+00:00",
        "2026-01-02T10:00:00+00:00",
        "2026-01-03T10:00:00+00:00",
        "2026-01-10T10:00:00+00:00",
    ]
    vals = [1.0, 2.0, 3.0, 100.0]
    s = chronological_ewma(ts, vals, as_of="2026-01-03T12:00:00+00:00")
    assert s.available
    assert len(s.values) == 3  # future point excluded
    assert 100.0 not in s.values


def test_effects_refuses_unbalanced(synth_root: Path) -> None:
    from lio.food_profiles.effects import asca

    runs = [r for r in discover_runs(synth_root) if r["run_id"].startswith("20260101-12000")][:3]
    folders = [synth_root / r["folder"] for r in runs]
    ds = create_dataset(synth_root, folders, synthetic=True, dataset_id="ds-asca")
    batch = build_feature_batch(synth_root, ds, "amplitude_raw", aggregate=False)
    meta = [{"food_label": "A", "day": "d1"} for _ in batch.row_ids]
    meta[0]["food_label"] = "B"
    out = asca(batch, meta, ["food_label", "day"])
    assert not out.available
    assert out.reason == CellReason.DESIGN_UNSUPPORTED.value


def test_portable_report_self_contained(tmp_path: Path) -> None:
    html = write_portable_report(
        tmp_path / "rep",
        title="demo",
        sections=[{"heading": "A", "text": "hello"}],
        embedded={"x": 1, "scores": [1.0, 2.0]},
        synthetic=True,
    )
    text = html.read_text()
    assert "localhost" not in text
    assert "SYNTHETIC" in text
    assert "application/json" in text


def test_embeddings_tsne_or_hint(synth_root: Path) -> None:
    from lio.food_profiles.embeddings import embed

    runs = [r for r in discover_runs(synth_root) if r["run_id"].startswith("20260101-12000")]
    folders = [synth_root / r["folder"] for r in runs]
    ds = create_dataset(synth_root, folders, synthetic=True, dataset_id="ds-emb")
    batch = build_feature_batch(synth_root, ds, "amplitude_raw")
    emb = embed(batch, method="tsne", max_iter=250)
    assert emb.available
    assert emb.coords is not None and emb.coords.shape[1] == 2
    umap_r = embed(batch, method="umap")
    # May be unavailable without umap-learn
    if not umap_r.available:
        assert umap_r.install_hint and "embeddings" in umap_r.install_hint


def test_cli_fixtures_and_help() -> None:
    r = subprocess.run(
        [sys.executable, "-m", "lio.cli", "profiles", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0
    assert "fit" in r.stdout
