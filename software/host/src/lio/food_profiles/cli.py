"""Offline CLI for food-profile Explore / Compare / Food Map."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from lio.food_profiles.artifacts import verify_bundle, write_portable_report
from lio.food_profiles.metadata import (
    RunAnnotation,
    annotate_run,
    create_dataset,
    list_datasets,
    load_dataset,
    profile_analyses_root,
)
from lio.food_profiles.pipeline import (
    build_feature_batch,
    compare_runs_payload,
    distance_bundle,
    fit_dataset_fpca,
    fit_dataset_pca,
    gallery_payload,
    project_dataset_pca,
)
from lio.food_profiles.runs import discover_runs, findings_payload, heatmap_payload, open_run
from lio.food_profiles.schema import BUILTIN_RECIPES, finite_json


def _print(obj: Any) -> None:
    print(json.dumps(finite_json(obj), indent=2))


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.results_dir)
    runs = discover_runs(root)
    if args.runs:
        want = set(args.runs.split(","))
        runs = [r for r in runs if r["run_id"] in want or r["folder"] in want]
    if args.all_synthetic:
        runs = [r for r in runs if r.get("synthetic")]
    folders = [root / r["folder"] for r in runs]
    if not folders:
        print("no runs found", file=sys.stderr)
        return 1
    anns = {}
    for r in runs:
        folder = root / r["folder"]
        meta = json.loads((folder / "scan.json").read_text())
        rid = r["run_id"]
        anns[rid] = RunAnnotation(
            run_id=rid,
            food_label=meta.get("food_label"),
            preparation_id=meta.get("preparation_id"),
            lot_id=meta.get("lot_id"),
            product_id=meta.get("sample_id"),
            repeat_type=meta.get("repeat_type"),
        )
    ds = create_dataset(
        root,
        folders,
        annotations=anns,
        notes=args.notes or "",
        synthetic=any(r.get("synthetic") for r in runs),
        dataset_id=args.out,
    )
    print(ds.dataset_id)
    return 0


def cmd_annotate(args: argparse.Namespace) -> int:
    root = Path(args.results_dir)
    ds = load_dataset(root, args.dataset)
    ann = RunAnnotation(
        run_id=args.run_id,
        food_label=args.food_label,
        preparation_id=args.preparation_id,
        lot_id=args.lot_id,
        product_id=args.product_id,
        parent_material_id=args.parent_material_id,
        repeat_type=args.repeat_type,
        notes=args.notes or "",
    )
    new = annotate_run(ds, root, ann)
    print(new.dataset_id)
    return 0


def cmd_explore(args: argparse.Namespace) -> int:
    run = open_run(Path(args.folder))
    out = {
        "run_id": run.run_id,
        "sample_id": run.sample_id,
        "synthetic": bool(run.meta.get("synthetic")),
        "channel_map_verified": run.channel_map_verified,
        "heatmap": {d: heatmap_payload(run, d) for d in ("opt101", "ingaas")},
        "findings": findings_payload(run),
    }
    _print(out)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    root = Path(args.results_dir)
    _print({"runs": discover_runs(root), "datasets": list_datasets(root)})
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    root = Path(args.results_dir)
    ds = load_dataset(root, args.dataset)
    batch = build_feature_batch(
        root, ds, args.recipe, reference_run_id=args.reference,
        include_proxy_h16=bool(getattr(args, "include_proxy_h16", False)),
    )  # fmt: skip
    out = (
        Path(args.out)
        if args.out
        else (profile_analyses_root(root) / f"{ds.dataset_id}_{args.recipe}")
    )
    from lio.food_profiles.artifacts import write_bundle

    write_bundle(
        out,
        kind="features",
        recipe=batch.recipe,
        arrays={"X": batch.X},
        payload=batch.to_jsonable(),
        synthetic=ds.synthetic,
    )
    print(out)
    return 0


def cmd_fit(args: argparse.Namespace) -> int:
    root = Path(args.results_dir)
    ds = load_dataset(root, args.dataset)
    out = (
        Path(args.out)
        if args.out
        else (profile_analyses_root(root) / f"{ds.dataset_id}_{args.method}")
    )
    if args.method == "pca":
        fit_dataset_pca(
            root,
            ds,
            args.recipe,
            n_components=args.n_components,
            scope=args.scope,
            reference_run_id=args.reference,
            out_dir=out,
        )
    elif args.method == "functional-pca":
        fit_dataset_fpca(
            root,
            ds,
            hole=args.hole,
            detector=args.detector,
            n_components=args.n_components,
            out_dir=out,
        )
    elif args.method in ("umap", "tsne"):
        from lio.food_profiles.artifacts import write_bundle
        from lio.food_profiles.embeddings import embed

        batch = build_feature_batch(root, ds, args.recipe)
        emb = embed(batch, method=args.method)
        arrays = {"coords": emb.coords} if emb.coords is not None else {"coords": np_empty()}
        write_bundle(
            out,
            kind=args.method,
            recipe=batch.recipe,
            arrays=arrays,
            payload=emb.to_jsonable(),
            synthetic=ds.synthetic,
        )
        if not emb.available:
            print(emb.reason, emb.install_hint or "", file=sys.stderr)
    else:
        print(f"unknown method {args.method}", file=sys.stderr)
        return 1
    print(out)
    return 0


def np_empty() -> Any:
    import numpy as np

    return np.zeros((0, 2))


def cmd_project(args: argparse.Namespace) -> int:
    root = Path(args.results_dir)
    ds = load_dataset(root, args.dataset)
    result = project_dataset_pca(root, ds, Path(args.model))
    out = Path(args.out) if args.out else profile_analyses_root(root) / f"{ds.dataset_id}_project"
    from lio.food_profiles.artifacts import write_bundle
    from lio.food_profiles.schema import Recipe

    meta, _, _ = __import__("lio.food_profiles.artifacts", fromlist=["load_bundle"]).load_bundle(
        Path(args.model)
    )
    write_bundle(
        out,
        kind="pca_projection",
        recipe=Recipe.from_dict(meta["recipe"]),
        arrays={"scores": result.scores, "residuals": result.residuals},
        payload=result.to_jsonable(),
        synthetic=ds.synthetic,
    )
    print(out)
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    root = Path(args.results_dir)
    ds = load_dataset(root, args.dataset)
    payload = compare_runs_payload(root, ds, args.a, args.b, args.recipe)
    if args.out:
        from lio.food_profiles.artifacts import write_bundle

        write_bundle(
            Path(args.out),
            kind="compare",
            recipe=BUILTIN_RECIPES.get(args.recipe, BUILTIN_RECIPES["amplitude_raw"]),
            arrays={"ok": [1]},
            payload=payload,
            synthetic=ds.synthetic,
        )
        print(args.out)
    else:
        _print(payload)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    root = Path(args.results_dir)
    ds = load_dataset(root, args.dataset)
    batch = build_feature_batch(
        root, ds, args.recipe, include_proxy_h16=bool(getattr(args, "include_proxy_h16", False))
    )
    labels, meta = _labels_and_groups(root, ds, batch)
    from lio.food_profiles.validation import validate_grouped

    result = validate_grouped(batch, labels, meta, target=args.target)
    _print(result.to_jsonable())
    return 0 if result.available else 2


def _labels_and_groups(root: Path, ds: Any, batch: Any) -> tuple[list[str], list[dict[str, Any]]]:
    labels: list[str] = []
    meta: list[dict[str, Any]] = []
    # Expand annotations onto aggregated rows via preparation / run
    for i, rid in enumerate(batch.run_ids):
        # run_ids may be comma-joined after aggregation
        first = rid.split(",")[0]
        ann = ds.annotations.get(first) or {}
        run_meta = {}
        try:
            from lio.food_profiles.metadata import resolve_run_folder

            run_meta = open_run(resolve_run_folder(root, ds, first)).meta
        except Exception:
            pass
        food = ann.get("food_label") or run_meta.get("food_label") or "unknown"
        labels.append(str(food))
        meta.append(
            {
                "preparation_id": batch.preparation_ids[i]
                or ann.get("preparation_id")
                or run_meta.get("preparation_id"),
                "lot_id": ann.get("lot_id") or run_meta.get("lot_id"),
                "day": (run_meta.get("started") or "")[:10],
                "food_label": food,
            }
        )
    return labels, meta


def cmd_effects(args: argparse.Namespace) -> int:
    root = Path(args.results_dir)
    ds = load_dataset(root, args.dataset)
    batch = build_feature_batch(root, ds, args.recipe)
    factors = [f.strip() for f in args.design.split(",") if f.strip()]
    meta = []
    for i, rid in enumerate(batch.run_ids):
        first = rid.split(",")[0]
        ann = ds.annotations.get(first) or {}
        try:
            from lio.food_profiles.metadata import resolve_run_folder

            rm = open_run(resolve_run_folder(root, ds, first)).meta
        except Exception:
            rm = {}
        meta.append(
            {
                "food_label": ann.get("food_label") or rm.get("food_label") or "unknown",
                "day": (rm.get("started") or "2026-01-01")[:10],
                "lot_id": ann.get("lot_id") or rm.get("lot_id") or "lot",
                "preparation_id": batch.preparation_ids[i],
            }
        )
    from lio.food_profiles.effects import asca

    result = asca(batch, meta, factors)
    if args.out:
        from lio.food_profiles.artifacts import write_bundle

        write_bundle(
            Path(args.out),
            kind="asca",
            recipe=batch.recipe,
            arrays={"residual_ss": [result.residual_ss]},
            payload=result.to_jsonable(),
            synthetic=ds.synthetic,
        )
        print(args.out)
    else:
        _print(result.to_jsonable())
    return 0 if result.available else 2


def cmd_trends(args: argparse.Namespace) -> int:
    root = Path(args.results_dir)
    ds = load_dataset(root, args.dataset)
    batch = build_feature_batch(root, ds, args.recipe, aggregate=False)
    # Use first finite feature as scalar trend
    timestamps = []
    values = []
    for i, rid in enumerate(batch.run_ids):
        try:
            from lio.food_profiles.metadata import resolve_run_folder

            rm = open_run(resolve_run_folder(root, ds, rid)).meta
        except Exception:
            rm = {}
        ts = rm.get("started") or rm.get("finished") or "2026-01-01T00:00:00+00:00"
        timestamps.append(str(ts))
        row = batch.X[i]
        finite = row[np_isfinite(row)]
        values.append(float(finite.mean()) if len(finite) else float("nan"))
    from lio.food_profiles.trends import chronological_ewma

    series = chronological_ewma(timestamps, values, as_of=args.as_of)
    if args.out:
        from lio.food_profiles.artifacts import write_bundle

        write_bundle(
            Path(args.out),
            kind="trends",
            recipe=batch.recipe,
            arrays={"values": values},
            payload=series.to_jsonable(),
            synthetic=ds.synthetic,
        )
        print(args.out)
    else:
        _print(series.to_jsonable())
    return 0 if series.available else 2


def np_isfinite(row: Any) -> Any:
    import numpy as np

    return np.isfinite(row)


def cmd_distances(args: argparse.Namespace) -> int:
    root = Path(args.results_dir)
    ds = load_dataset(root, args.dataset)
    out = Path(args.out) if args.out else None
    payload = distance_bundle(root, ds, args.recipe, metric=args.metric, out_dir=out)
    if out is None:
        _print(payload)
    else:
        print(out)
    return 0


def cmd_gallery(args: argparse.Namespace) -> int:
    root = Path(args.results_dir)
    ds = load_dataset(root, args.dataset)
    _print(gallery_payload(root, ds))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from lio.food_profiles.artifacts import load_bundle

    meta, arrays, payload = load_bundle(Path(args.bundle))
    out = Path(args.out)
    write_portable_report(
        out,
        title=f"LIO food-profile report: {meta.get('kind')}",
        sections=[
            {"heading": "Bundle", "text": f"id={meta.get('bundle_id')} kind={meta.get('kind')}"},
            {
                "heading": "Arrays",
                "text": ", ".join(f"{k}:{getattr(v, 'shape', None)}" for k, v in arrays.items()),
            },
        ],
        embedded={"meta": meta, "payload": payload},
        synthetic=bool(meta.get("synthetic")),
    )
    print(out / "report.html")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    result = verify_bundle(Path(args.bundle))
    _print(result)
    return 0 if result["ok"] else 1


def cmd_fixtures(args: argparse.Namespace) -> int:
    from lio.food_profiles.fixtures import build_fixture_library

    manifest = build_fixture_library(Path(args.out))
    _print(manifest)
    return 0


def cmd_ablate(args: argparse.Namespace) -> int:
    """Held-out ablation of ``proxy_unassigned:`` (h16) features."""
    from lio.food_profiles.ablation import held_out_proxy_ablation, proxy_predictive_comparison
    from lio.food_profiles.pipeline import build_feature_batch

    if not getattr(args, "include_proxy_h16", False):
        raise SystemExit("ablate needs the explicit --include-proxy-h16 opt-in")
    root = Path(args.results_dir)
    ds = load_dataset(root, args.dataset)
    batch = build_feature_batch(root, ds, args.recipe, reference_run_id=args.reference,
                                include_proxy_h16=True)  # fmt: skip
    result = held_out_proxy_ablation(batch, metric=args.metric)
    labels, meta = _labels_and_groups(root, ds, batch)
    _print({"descriptive": result.to_dict(),
            "predictive": proxy_predictive_comparison(batch, labels, meta)})  # fmt: skip
    return 0


def cmd_baseline(args: argparse.Namespace) -> int:
    """Select a compatible baseline for quantitative reuse or raw compare."""
    from lio.food_profiles.baselines import (
        BaselineKind,
        BaselineUse,
        candidate_from_run_folder,
        select_baseline,
    )

    root = Path(args.results_dir)
    cands = [candidate_from_run_folder(root / p) for p in args.candidates]
    use = BaselineUse.QUANTITATIVE if args.use == "quantitative" else BaselineUse.RAW_COMPARE
    kind = BaselineKind(args.kind) if args.kind else None
    decision = select_baseline(
        cands,
        use=use,
        require_kind=kind,
        require_config_sha256=args.config_sha256,
        require_calibration_id=args.calibration_id,
        require_model=args.model,
        require_geometry_key=args.geometry_key,
        require_reference_protocol=args.reference_protocol,
    )
    _print(decision.to_dict())
    return 0 if decision.ok else 1


def build_profiles_parser(sub: Any, *, fn: Any = None) -> None:
    p = sub.add_parser("profiles", help="offline food-profile Explore / Compare / Food Map")
    if fn is not None:
        p.set_defaults(fn=fn)
    ss = p.add_subparsers(dest="profiles_command", required=True)
    # Shared --results-dir after the subcommand: `lio profiles init --results-dir ROOT …`
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--results-dir", default="test_results", help="results root")

    c = ss.add_parser("fixtures", help="write labeled synthetic run library", parents=[common])
    c.add_argument("--out", required=True)
    c.set_defaults(profiles_fn=cmd_fixtures)

    c = ss.add_parser("list", help="list runs and datasets", parents=[common])
    c.set_defaults(profiles_fn=cmd_list)

    c = ss.add_parser("explore", help="inspect one run folder (JSON)", parents=[common])
    c.add_argument("folder")
    c.set_defaults(profiles_fn=cmd_explore)

    c = ss.add_parser("init", help="create immutable dataset from runs", parents=[common])
    c.add_argument("--out", default=None, help="dataset id")
    c.add_argument("--runs", default=None, help="comma run_ids")
    c.add_argument("--all-synthetic", action="store_true")
    c.add_argument("--notes", default="")
    c.set_defaults(profiles_fn=cmd_init)

    c = ss.add_parser("annotate", help="new dataset version with annotation", parents=[common])
    c.add_argument("dataset")
    c.add_argument("--run-id", required=True)
    c.add_argument("--food-label")
    c.add_argument("--preparation-id")
    c.add_argument("--lot-id")
    c.add_argument("--product-id")
    c.add_argument("--parent-material-id")
    c.add_argument("--repeat-type")
    c.add_argument("--notes", default="")
    c.set_defaults(profiles_fn=cmd_annotate)

    c = ss.add_parser("build", help="extract feature matrix for a recipe", parents=[common])
    c.add_argument("dataset")
    c.add_argument("--recipe", default="amplitude_raw")
    c.add_argument("--reference", default=None)
    c.add_argument("--out", default=None)
    c.add_argument(
        "--include-proxy-h16",
        action="store_true",
        help="explicit opt-in: h16 as proxy_unassigned, never primary 1850",
    )
    c.set_defaults(profiles_fn=cmd_build)

    c = ss.add_parser("fit", help="fit pca|functional-pca|umap|tsne", parents=[common])
    c.add_argument("dataset")
    c.add_argument("--recipe", default="amplitude_raw")
    c.add_argument("--method", default="pca", choices=["pca", "functional-pca", "umap", "tsne"])
    c.add_argument("--n-components", type=int, default=2)
    c.add_argument("--scope", default="fused", choices=["fused", "opt101", "ingaas"])
    c.add_argument("--hole", type=int, default=5)
    c.add_argument("--detector", default="opt101")
    c.add_argument("--reference", default=None)
    c.add_argument("--out", default=None)
    c.set_defaults(profiles_fn=cmd_fit)

    c = ss.add_parser("project", help="project dataset through frozen PCA bundle", parents=[common])
    c.add_argument("--dataset", required=True)
    c.add_argument("--model", required=True)
    c.add_argument("--out", default=None)
    c.set_defaults(profiles_fn=cmd_project)

    c = ss.add_parser("compare", help="compare two runs in a dataset", parents=[common])
    c.add_argument("dataset")
    c.add_argument("--a", required=True)
    c.add_argument("--b", required=True)
    c.add_argument("--recipe", default="amplitude_raw")
    c.add_argument("--out", default=None)
    c.set_defaults(profiles_fn=cmd_compare)

    c = ss.add_parser("validate", help="grouped leave-one-group-out evaluation", parents=[common])
    c.add_argument("dataset")
    c.add_argument("--recipe", default="amplitude_raw")
    c.add_argument(
        "--target",
        default="new-preparation",
        choices=["new-preparation", "new-lot", "new-day", "new-food"],
    )
    c.add_argument(
        "--include-proxy-h16",
        action="store_true",
        help="explicit opt-in: h16 as proxy_unassigned, never primary 1850",
    )
    c.set_defaults(profiles_fn=cmd_validate)

    c = ss.add_parser("effects", help="ASCA for balanced crossed designs", parents=[common])
    c.add_argument("dataset")
    c.add_argument("--recipe", default="amplitude_raw")
    c.add_argument("--design", required=True, help="comma factors, e.g. food_label,day")
    c.add_argument("--out", default=None)
    c.set_defaults(profiles_fn=cmd_effects)

    c = ss.add_parser(
        "trends", help="chronological EWMA (as-of truncates future)", parents=[common]
    )
    c.add_argument("dataset")
    c.add_argument("--recipe", default="amplitude_raw")
    c.add_argument("--as-of", required=True)
    c.add_argument("--out", default=None)
    c.set_defaults(profiles_fn=cmd_trends)

    c = ss.add_parser(
        "distances", help="pairwise distances + optional clustering", parents=[common]
    )
    c.add_argument("dataset")
    c.add_argument("--recipe", default="amplitude_raw")
    c.add_argument("--metric", default="euclidean")
    c.add_argument("--out", default=None)
    c.set_defaults(profiles_fn=cmd_distances)

    c = ss.add_parser("gallery", help="food / preparation gallery JSON", parents=[common])
    c.add_argument("dataset")
    c.set_defaults(profiles_fn=cmd_gallery)

    c = ss.add_parser("report", help="portable self-contained HTML report")
    c.add_argument("bundle")
    c.add_argument("--out", required=True)
    c.set_defaults(profiles_fn=cmd_report)

    c = ss.add_parser("verify", help="verify bundle schema / arrays")
    c.add_argument("bundle")
    c.set_defaults(profiles_fn=cmd_verify)

    c = ss.add_parser(
        "ablate",
        help="held-out ablation of proxy_unassigned: (h16) features",
        parents=[common],
    )
    c.add_argument("dataset")
    c.add_argument("--recipe", default="amplitude_raw")
    c.add_argument("--reference", default=None)
    c.add_argument("--metric", default="mean_pairwise_distance")
    c.add_argument(
        "--include-proxy-h16",
        action="store_true",
        help="explicit opt-in: h16 as proxy_unassigned, never primary 1850",
    )
    c.set_defaults(profiles_fn=cmd_ablate)

    c = ss.add_parser(
        "baseline",
        help="select compatible baseline (rejects incomplete for quantitative reuse)",
        parents=[common],
    )
    c.add_argument("candidates", nargs="+", help="run folders relative to --results-dir")
    c.add_argument("--use", default="quantitative", choices=["quantitative", "raw_compare"])
    c.add_argument(
        "--kind",
        default=None,
        choices=["suite_yaml", "scan_baseline", "empty_holder", "white_reference", "unknown"],
    )
    c.add_argument("--config-sha256", default=None)
    c.add_argument("--calibration-id", default=None)
    c.add_argument("--model", default=None)
    c.add_argument("--geometry-key", default=None)
    c.add_argument("--reference-protocol", default=None)
    c.set_defaults(profiles_fn=cmd_baseline)


def cmd_profiles(args: argparse.Namespace) -> int:
    return int(args.profiles_fn(args))
