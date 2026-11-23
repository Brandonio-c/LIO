"""Fixed-height amplitude, O-envelope and curve-summary feature extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from lio.food_profiles.runs import RunData
from lio.food_profiles.schema import (
    BUILTIN_RECIPES,
    DETECTORS,
    CellReason,
    FeatureId,
    Recipe,
    finite_json,
)


@dataclass
class FeatureBatch:
    row_ids: list[str]
    run_ids: list[str]
    preparation_ids: list[str | None]
    feature_ids: list[str]
    X: np.ndarray  # (n_rows, n_features), float64 with NaN for unavailable
    reasons: np.ndarray  # object array of CellReason values
    source_links: list[dict[str, Any]]
    recipe: Recipe
    warnings: list[str] = field(default_factory=list)
    units: str = "counts"

    @property
    def n_rows(self) -> int:
        return len(self.row_ids)

    @property
    def n_features(self) -> int:
        return len(self.feature_ids)

    def to_jsonable(self) -> dict[str, Any]:
        avail = np.isfinite(self.X)
        return finite_json(
            {
                "row_ids": self.row_ids,
                "run_ids": self.run_ids,
                "preparation_ids": self.preparation_ids,
                "feature_ids": self.feature_ids,
                "X": [
                    [
                        None if not avail[i, j] else float(self.X[i, j])
                        for j in range(self.n_features)
                    ]
                    for i in range(self.n_rows)
                ],
                "reasons": self.reasons.tolist(),
                "source_links": self.source_links,
                "recipe": self.recipe.to_dict(),
                "warnings": self.warnings,
                "units": self.units,
            }
        )


def _common_heights(run: RunData, recipe: Recipe) -> list[float]:
    heights: set[float] | None = None
    for det in recipe.detectors:
        hs: set[float] = set()
        for _, r in run.iter_selected(recipe.selection):
            if r.get("detector") != det:
                continue
            try:
                hole = int(float(r["hole"]))
                if run.is_blind(hole, det):
                    continue
                hs.add(float(r["height_hs"]))
            except (KeyError, ValueError):
                continue
        heights = hs if heights is None else (heights & hs)
    return sorted(heights or [])


def _nets_at_height(
    run: RunData, recipe: Recipe, height_hs: float
) -> dict[tuple[str, int], tuple[float, str]]:
    """Mean net at exact height for each (detector, hole)."""
    acc: dict[tuple[str, int], list[tuple[float, str]]] = {}
    for i, r in run.iter_selected(recipe.selection):
        try:
            if abs(float(r["height_hs"]) - height_hs) > 1e-9:
                continue
            det = r["detector"]
            hole = int(float(r["hole"]))
            net = float(r["net_counts"])
        except (KeyError, ValueError):
            continue
        acc.setdefault((det, hole), []).append((net, run.row_id(i)))
    out: dict[tuple[str, int], tuple[float, str]] = {}
    for k, vals in acc.items():
        out[k] = (float(np.mean([v[0] for v in vals])), vals[0][1])
    return out


def _o_from_analysis(run: RunData) -> dict[tuple[str, int], float]:
    if not run.analysis_ok or not run.analysis:
        return {}
    out: dict[tuple[str, int], float] = {}
    for f in run.analysis.get("findings") or []:
        fid = str(f.get("id") or "")
        # optics/<det>/hNN/response
        parts = fid.split("/")
        if (
            len(parts) >= 4
            and parts[0] == "optics"
            and parts[1] in DETECTORS
            and parts[2].startswith("h")
        ):
            if parts[3] != "response":
                continue
            det = parts[1]
            hole = int(parts[2][1:])
            data = f.get("data") or {}
            if "O" in data and data["O"] is not None:
                out[(det, hole)] = float(data["O"])
    return out


def _c_from_analysis(run: RunData) -> dict[str, float]:
    """Per-detector coupling C if present in analysis findings/context."""
    if not run.analysis_ok or not run.analysis:
        return {}
    ctx = (run.analysis.get("context") or {}).get("electrical") or {}
    coup = ctx.get("coupling") or {}
    out: dict[str, float] = {}
    for det in DETECTORS:
        if det in coup and isinstance(coup[det], dict) and "C" in coup[det]:
            out[det] = float(coup[det]["C"])
        elif det in coup and isinstance(coup[det], (int, float)):
            out[det] = float(coup[det])
    # Fallback: find elec/<det>/coupling findings
    for f in run.analysis.get("findings") or []:
        fid = str(f.get("id") or "")
        if fid.startswith("elec/") and fid.endswith("/coupling"):
            det = fid.split("/")[1]
            data = f.get("data") or {}
            if "C" in data:
                out[det] = float(data["C"])
            elif f.get("value") is not None:
                out[det] = float(f["value"])
    return out


def feature_ids_for_recipe(
    recipe: Recipe,
    heights: list[float] | None = None,
    *,
    include_hole: dict[tuple[str, int], bool] | None = None,
    include_proxy_h16: bool = False,
) -> list[FeatureId]:
    """Feature schema. Structural blinds are omitted (masked), not stored as NaN zeros.

    H16 is excluded from the primary feature schema by default (D18). Pass
    ``include_proxy_h16=True`` for explicit opt-in ``proxy_unassigned:`` extraction.
    """
    ids: list[FeatureId] = []
    if recipe.representation == "o_envelope":
        for det in recipe.detectors:
            for hole in range(1, 17):
                if hole == 16 and not include_proxy_h16:
                    continue
                if include_hole is not None and not include_hole.get((det, hole), True):
                    continue
                ids.append(FeatureId(det, hole, kind="o_envelope", recipe=recipe.name))
        return ids
    h_list = heights or [0.0]
    h0 = h_list[0] if h_list else 0.0
    for det in recipe.detectors:
        for hole in range(1, 17):
            if hole == 16 and not include_proxy_h16:
                continue
            if include_hole is not None and not include_hole.get((det, hole), True):
                continue
            ids.append(FeatureId(det, hole, kind="net", height_hs=h0, recipe=recipe.name))
    return ids


def signal_hole_mask(
    run: RunData,
    recipe: Recipe,
    *,
    include_proxy_h16: bool = False,
) -> dict[tuple[str, int], bool]:
    out: dict[tuple[str, int], bool] = {}
    for det in recipe.detectors:
        for hole in range(1, 17):
            if hole == 16 and not include_proxy_h16:
                out[(det, hole)] = False
                continue
            out[(det, hole)] = not run.is_blind(hole, det)
    return out


def extract_run_vector(
    run: RunData,
    recipe: Recipe | str,
    *,
    reference: RunData | None = None,
    preparation_id: str | None = None,
    include_proxy_h16: bool = False,
) -> FeatureBatch:
    if isinstance(recipe, str):
        recipe = BUILTIN_RECIPES[recipe]
    warnings: list[str] = []
    if not run.channel_map_verified:
        warnings.append("channel_map_unverified")
    if include_proxy_h16:
        warnings.append("h16_proxy_opt_in:proxy_unassigned_never_primary1850")
    else:
        warnings.append("h16_excluded_from_primary_features")

    holes = signal_hole_mask(run, recipe, include_proxy_h16=include_proxy_h16)

    if recipe.representation == "o_envelope":
        o_map = _o_from_analysis(run)
        fids = feature_ids_for_recipe(
            recipe, include_hole=holes, include_proxy_h16=include_proxy_h16
        )
        X = np.full((1, len(fids)), np.nan)
        reasons = np.empty((1, len(fids)), dtype=object)
        links: list[dict[str, Any]] = [{}]
        if not run.analysis_ok:
            for j, _fid in enumerate(fids):
                reasons[0, j] = CellReason.INSUFFICIENT_ANALYSIS.value
            warnings.append(f"analysis_{run.analysis_reason}")
        else:
            for j, fid in enumerate(fids):
                if (fid.detector, fid.hole) not in o_map:
                    reasons[0, j] = CellReason.MISSING.value
                else:
                    X[0, j] = o_map[(fid.detector, fid.hole)]
                    reasons[0, j] = CellReason.OK.value
        return FeatureBatch(
            row_ids=[f"{run.run_id}:o_envelope"],
            run_ids=[run.run_id],
            preparation_ids=[preparation_id],
            feature_ids=[f.key for f in fids],
            X=X,
            reasons=reasons,
            source_links=links,
            recipe=recipe,
            warnings=warnings,
            units="O_counts",
        )

    heights = _common_heights(run, recipe)
    # Optional locked fingerprint height (dataset-aligned)
    locked = getattr(extract_run_vector, "_lock_height_hs", None)
    if locked is not None:
        h0 = float(locked)
        if not heights or min(abs(h - h0) for h in heights) > 1e-9:
            fids = feature_ids_for_recipe(
                recipe, [h0], include_hole=holes, include_proxy_h16=include_proxy_h16
            )
            X = np.full((1, len(fids)), np.nan)
            reasons = np.full((1, len(fids)), CellReason.UNSUPPORTED_HEIGHT.value, dtype=object)
            return FeatureBatch(
                [f"{run.run_id}:unsupported_h"],
                [run.run_id],
                [preparation_id],
                [f.key for f in fids],
                X,
                reasons,
                [{}],
                recipe,
                [*warnings, "height_not_in_run"],
            )
    elif not heights:
        fids = feature_ids_for_recipe(
            recipe, [0.0], include_hole=holes, include_proxy_h16=include_proxy_h16
        )
        X = np.full((1, len(fids)), np.nan)
        reasons = np.full((1, len(fids)), CellReason.MISSING.value, dtype=object)
        return FeatureBatch(
            [f"{run.run_id}:empty"],
            [run.run_id],
            [preparation_id],
            [f.key for f in fids],
            X,
            reasons,
            [{}],
            recipe,
            [*warnings, "no_common_heights"],
        )
    else:
        # Default fingerprint height: median of common heights (stable geometric mid-travel)
        h0 = float(heights[len(heights) // 2])
    fids = feature_ids_for_recipe(
        recipe, [h0], include_hole=holes, include_proxy_h16=include_proxy_h16
    )
    fids = [
        FeatureId(f.detector, f.hole, kind=f.kind, height_hs=h0, recipe=recipe.name) for f in fids
    ]
    nets = _nets_at_height(run, recipe, h0)
    c_map = _c_from_analysis(run) if recipe.coupling_policy == "analysis_c" else {}
    ref_nets: dict[tuple[str, int], tuple[float, str]] = {}
    ref_c: dict[str, float] = {}
    if recipe.representation == "reference_relative":
        if reference is None:
            warnings.append("reference_required")
        else:
            ref_nets = _nets_at_height(reference, recipe, h0)
            if recipe.coupling_policy == "analysis_c":
                ref_c = _c_from_analysis(reference)

    X = np.full((1, len(fids)), np.nan)
    reasons = np.empty((1, len(fids)), dtype=object)
    link: dict[str, Any] = {"height_hs": h0, "rows": {}}
    # D07: InGaAs physical/quantitative/reference gated when Rf unknown or A0 unverified.
    quant_gate = _quantity_gate_from_run(run)
    for j, fid in enumerate(fids):
        key = (fid.detector, fid.hole)
        if key not in nets:
            reasons[0, j] = CellReason.MISSING.value
            continue
        net, rid = nets[key]
        link["rows"][fid.key] = rid
        if recipe.representation == "reference_relative":
            if reference is None:
                reasons[0, j] = CellReason.INCOMPATIBLE_REFERENCE.value
                continue
            if key not in ref_nets:
                reasons[0, j] = CellReason.INCOMPATIBLE_REFERENCE.value
                continue
            if not _ingaas_ratio_allowed(fid.detector, quant_gate):
                reasons[0, j] = CellReason.DESIGN_UNSUPPORTED.value
                warnings.append(
                    f"{fid.key}: InGaAs quantitative/reference blocked "
                    f"({quant_gate.get('reason', 'unverified')})"
                )
                continue
            c_s = c_map.get(fid.detector, 0.0) if recipe.coupling_policy == "analysis_c" else 0.0
            c_r = ref_c.get(fid.detector, 0.0) if recipe.coupling_policy == "analysis_c" else 0.0
            if recipe.coupling_policy == "analysis_c" and (
                fid.detector not in c_map or fid.detector not in ref_c
            ):
                reasons[0, j] = CellReason.INSUFFICIENT_ANALYSIS.value
                continue
            num = net - c_s
            den = ref_nets[key][0] - c_r
            if not np.isfinite(den) or den <= recipe.min_reference_denom:
                reasons[0, j] = CellReason.WEAK_DENOMINATOR.value
                continue
            X[0, j] = num / den
            reasons[0, j] = CellReason.OK.value
        else:
            if recipe.coupling_policy == "analysis_c":
                if fid.detector not in c_map:
                    reasons[0, j] = CellReason.INSUFFICIENT_ANALYSIS.value
                    continue
                if not _ingaas_ratio_allowed(fid.detector, quant_gate):
                    # Preserve raw counts path: fall back to net, mark unsupported for O.
                    reasons[0, j] = CellReason.DESIGN_UNSUPPORTED.value
                    warnings.append(
                        f"{fid.key}: InGaAs physical current/optics blocked; raw counts retained"
                    )
                    X[0, j] = net
                    continue
                X[0, j] = net - c_map[fid.detector]
            else:
                X[0, j] = net
            reasons[0, j] = CellReason.OK.value

    return FeatureBatch(
        row_ids=[f"{run.run_id}:h{h0:g}"],
        run_ids=[run.run_id],
        preparation_ids=[preparation_id],
        feature_ids=[f.key for f in fids],
        X=X,
        reasons=reasons,
        source_links=[link],
        recipe=recipe,
        warnings=warnings,
        units="ratio" if recipe.representation == "reference_relative" else "counts",
    )


def stack_batches(batches: list[FeatureBatch]) -> FeatureBatch:
    if not batches:
        raise ValueError("no batches")
    # Require identical feature_ids
    fids = batches[0].feature_ids
    for b in batches[1:]:
        if b.feature_ids != fids:
            raise ValueError("feature_ids mismatch across batches")
    return FeatureBatch(
        row_ids=[r for b in batches for r in b.row_ids],
        run_ids=[r for b in batches for r in b.run_ids],
        preparation_ids=[p for b in batches for p in b.preparation_ids],
        feature_ids=fids,
        X=np.vstack([b.X for b in batches]),
        reasons=np.vstack([b.reasons for b in batches]),
        source_links=[s for b in batches for s in b.source_links],
        recipe=batches[0].recipe,
        warnings=[w for b in batches for w in b.warnings],
        units=batches[0].units,
    )


def _quantity_gate_from_run(run: RunData) -> dict[str, Any]:
    """Collect Rf / A0 facts for quantity eligibility (D07)."""
    from lio.scan.provenance import Quantity, RfProvenance, quantity_eligibility

    snap = (run.meta or {}).get("acquisition_snapshot") or {}
    adc = snap.get("adc") or {}
    rf_raw = (snap.get("rf") or {}).get("ingaas") or {}
    if isinstance(rf_raw, dict):
        rf = RfProvenance(
            rf_raw.get("value_ohm"),
            str(rf_raw.get("state") or "unknown"),
            str(rf_raw.get("note") or ""),
        )
    else:
        rf = RfProvenance(None, "unknown", "missing")
    input_range = str((snap.get("input_range") or {}).get("ingaas") or "unverified")
    lsb = adc.get("lsb_mv")
    elig = quantity_eligibility(
        Quantity.MATCHED_RATIO,
        detector="ingaas",
        lsb_mv=None if lsb is None else float(lsb),
        rf=rf,
        input_range=input_range,
        geometry_compatible=bool(snap.get("assembly")),
        control_evidence=False,
    )
    return {
        "eligible": elig.eligible,
        "reason": elig.reason,
        "input_range": input_range,
        "rf_state": rf.state,
    }


def _ingaas_ratio_allowed(detector: str, gate: dict[str, Any]) -> bool:
    if detector != "ingaas":
        return True  # OPT101 remains independently available
    return bool(gate.get("eligible"))


def aggregate_by_preparation(batch: FeatureBatch) -> FeatureBatch:
    """Equal-weight mean of technical runs within each known preparation_id."""
    groups: dict[str, list[int]] = {}
    ungrouped: list[int] = []
    for i, prep in enumerate(batch.preparation_ids):
        if prep:
            groups.setdefault(prep, []).append(i)
        else:
            ungrouped.append(i)
    row_ids: list[str] = []
    run_ids: list[str] = []
    preps: list[str | None] = []
    rows_x: list[np.ndarray] = []
    rows_r: list[np.ndarray] = []
    links: list[dict[str, Any]] = []
    warnings = list(batch.warnings)
    for prep, idxs in groups.items():
        sub = batch.X[idxs]
        mask = np.isfinite(sub)
        mean = np.full(batch.n_features, np.nan)
        for j in range(batch.n_features):
            cols = sub[mask[:, j], j]
            if len(cols):
                mean[j] = float(np.mean(cols))
        reason = np.array(
            [
                CellReason.OK.value if np.isfinite(mean[j]) else CellReason.MISSING.value
                for j in range(batch.n_features)
            ],
            dtype=object,
        )
        row_ids.append(f"prep:{prep}")
        run_ids.append(",".join(batch.run_ids[i] for i in idxs))
        preps.append(prep)
        rows_x.append(mean)
        rows_r.append(reason)
        links.append({"members": [batch.row_ids[i] for i in idxs], "reducer": "mean"})
    for i in ungrouped:
        row_ids.append(batch.row_ids[i])
        run_ids.append(batch.run_ids[i])
        preps.append(None)
        rows_x.append(batch.X[i])
        rows_r.append(batch.reasons[i])
        links.append(batch.source_links[i])
        warnings.append(CellReason.INDEPENDENCE_UNKNOWN.value)
    return FeatureBatch(
        row_ids,
        run_ids,
        preps,
        batch.feature_ids,
        np.vstack(rows_x) if rows_x else np.zeros((0, batch.n_features)),
        np.vstack(rows_r) if rows_r else np.empty((0, batch.n_features), dtype=object),
        links,
        batch.recipe,
        warnings,
        batch.units,
    )
