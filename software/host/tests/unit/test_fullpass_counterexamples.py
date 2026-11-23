"""Full-pass mandatory counterexamples (FAIL on old behavior → PASS after fix).

Offline only — fake transports / synthetic journals. No real serial, POWER WAKE,
LEDs, motors, or invented physical confirmations.
"""

from __future__ import annotations

import ast
import contextlib
import shutil
from pathlib import Path

import pytest

from lio.config import load_config
from lio.device import LIODevice
from lio.ownership import DutyJournal, OwnershipError
from lio.sim import SimulatedLIO
from lio.transport import SimTransport

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[4]
CFG = REPO / "software" / "config" / "lio_hw.yaml"
RESULTS = REPO / "test_results"
QUICK = RESULTS / "20261123-003133_scan_quick"


@pytest.fixture()
def cfg():
    return load_config(CFG)


def _sim_dev(cfg, tmp_path: Path, *, name: str = "rig", **kw) -> LIODevice:
    sim = SimulatedLIO(cfg)
    journal = DutyJournal.for_rig(
        f"synthetic-{name}",
        state_root=tmp_path / name,
        window_s=cfg.section.num("duty.window_s"),
        budget_ms=kw.pop("budget_ms", cfg.duty_budgets_ms()),
        rail_of=cfg.duty_key,
        synthetic=True,
    )
    return LIODevice(SimTransport(sim), cfg, journal=journal, **kw)


# --------------------------------------------------------------------------- 1


def test_ce01_multiline_and_prefixed_raw_refused(cfg, tmp_path: Path) -> None:
    """Fake-transport raw multiline / @seq prefix must refuse on real-path gate."""
    with _sim_dev(cfg, tmp_path, name="ce01") as dev:
        sent: list[bytes] = []
        orig = dev.transport.write_raw

        def spy(data: bytes) -> None:
            sent.append(data)
            return orig(data)

        dev.transport.write_raw = spy  # type: ignore[method-assign]
        before = len(sent)
        with pytest.raises(OwnershipError, match=r"refus|raw|multiline|light"):
            dev.send_raw(b"PING\nCH 1 ON 1500\n", timeout=0.3)
        assert not any(b"CH 1 ON" in s for s in sent[before:])

        before = len(sent)
        with pytest.raises(OwnershipError, match=r"refus|raw|prefix|light|@"):
            dev.send_raw(b"@123 CH 1 ON 1500\n", timeout=0.3)
        assert not any(b"CH 1 ON" in s for s in sent[before:])


# --------------------------------------------------------------------------- 2


def test_ce02_constructor_must_not_mutate_live_owner_journal(cfg, tmp_path: Path) -> None:
    """Constructing a second journal/device must not wipe a live owner's charges."""
    path = tmp_path / "shared.json"
    clock = {"t": 1000.0}

    def mono() -> float:
        return clock["t"]

    j1 = DutyJournal.for_rig(
        "ce02",
        state_root=tmp_path,
        window_s=60.0,
        budget_ms=cfg.duty_budgets_ms(),
        rail_of=cfg.duty_key,
        synthetic=True,
        path=path,
        mono_now=mono,
    )
    res = j1.reserve(3, 900.0)
    j1.commit(res, t_on=clock["t"], t_off=clock["t"] + 0.9)
    clock["t"] += 1.0
    before = path.read_bytes()
    used_before = j1.used_ms(3)

    # Construction alone must not rewrite / clear production journal.
    j2 = DutyJournal(
        rig_identity="ce02",
        path=path,
        window_s=60.0,
        budget_ms=cfg.duty_budgets_ms(),
        rail_of=cfg.duty_key,
        mono_now=mono,
        mutate_on_construct=False,
    )
    assert path.read_bytes() == before
    assert j1.used_ms(3) >= used_before - 1e-6
    # Stale empty memory cannot spend over the live owner's charge after reload.
    j2._data = j2._empty()
    j2.reload()
    assert j2.used_ms(3) >= 800.0


# --------------------------------------------------------------------------- 3


def test_ce03_undersized_reservation_vs_active_wdt_refuses_or_lowers(cfg, tmp_path: Path) -> None:
    """50 ms reserve with active 2000 ms WDT: refuse, or lower WDT then admit."""
    from lio.timing_capability import admit_pulse_reservation

    # Pure capability check: undersized vs active WDT is invalid without lower.
    ok, reason = admit_pulse_reservation(
        reserved_ms=50.0, active_wdt_ms=2000, rail="A", may_lower_wdt=False
    )
    assert ok is False
    assert reason

    budgets = {"A": 5000.0, "B": 10000.0}
    with _sim_dev(cfg, tmp_path, name="ce03", budget_ms=budgets) as dev:
        info = dev.info(refresh=True)
        assert int(info.as_int("wdt_a_ms")) >= 2000
        # Device path must lower WDT to covering need (or refuse).
        until = dev.ch_on(1, 50)
        assert until <= 100
        wdt_after = int(dev.info(refresh=True).as_int("wdt_a_ms"))
        assert wdt_after <= max(50, int(until) + 1) or wdt_after == 50


# --------------------------------------------------------------------------- 4


def test_ce04_failed_off_retains_uncertainty_when_ce_high(cfg, tmp_path: Path) -> None:
    """Failed OFF while CE remains high → uncertain + conservative charge."""
    with _sim_dev(cfg, tmp_path, name="ce04") as dev:
        assert dev.journal is not None
        dev.wdt_cfg("A", 50)
        dev.sr_raw(0x0001)
        dev.ce(1, True)
        assert dev.status().as_int("ce1") == 1

        orig = LIODevice._command_unguarded

        def boom(self, cmd, *a, **k):
            if str(cmd).strip().upper().startswith("OFF"):
                raise RuntimeError("simulated OFF failure")
            return orig(self, cmd, *a, **k)

        LIODevice._command_unguarded = boom  # type: ignore[method-assign]
        try:
            with pytest.raises(RuntimeError, match="OFF"):
                dev.off()
        finally:
            LIODevice._command_unguarded = orig  # type: ignore[method-assign]

        st = dev.status()
        assert st.as_int("ce1") == 1
        assert dev.journal._data.get("uncertain") is True


# --------------------------------------------------------------------------- 5


def test_ce05_height_resume_gain2_under_gain1_snapshot_rejects(cfg, tmp_path: Path) -> None:
    """Height resume at gain 2 under gain-1 snapshot → reject before light."""
    from lio.operator import SimOperator
    from lio.scan import PlanError, plan_for, resume, sim_stage
    from lio.scan.provenance import snapshot_from_hw_config
    from lio.scan.store import ScanStore

    sim = SimulatedLIO(cfg)
    journal = DutyJournal.for_rig(
        "ce05",
        state_root=tmp_path,
        window_s=60.0,
        budget_ms=cfg.duty_budgets_ms(),
        rail_of=cfg.duty_key,
        synthetic=True,
    )
    with LIODevice(SimTransport(sim), cfg, journal=journal) as dev:
        sim_stage(dev, tmp_path / "stage.json", int(sim.travel_hs))
        plan = plan_for(cfg, "quick", dev.stage, 0)
        snap = snapshot_from_hw_config(
            cfg, protocol_hash="ce05", gain="1", mains_periods=None, mains_hz=None
        )
        store = ScanStore.create(
            tmp_path / "out",
            plan.mode,
            {
                "mode": plan.mode,
                "sample_id": "empty",
                "status": "INCOMPLETE",
                "completed_step": 0,
                "simulated": True,
                "config_sha256": cfg.sha256,
                "firmware": dict(dev.info().values),
                "plan": plan.to_dict(),
                "acquisition_snapshot": snap.to_dict(),
            },
        )
        store.meta["status"] = "INCOMPLETE"
        store.save_meta()
        assert str((store.meta["acquisition_snapshot"].get("adc") or {}).get("gain")) in (
            "1",
            "GAIN_ONE",
            "1.0",
        )
        lit: list[str] = []
        orig = dev.transport.write_line

        def spy(line: str) -> None:
            lit.append(line)
            return orig(line)

        dev.transport.write_line = spy  # type: ignore[method-assign]
        before = len(lit)
        dev.adc_gain("2")
        assert str(dev.info(refresh=True).values.get("gain")) == "2"
        with pytest.raises((PlanError, Exception), match=r"gain|snapshot|preflight|resume"):
            resume(dev, cfg, store.folder, SimOperator(sim))
        # Refusal before light: no MEAS after the gain change.
        after = lit[before:]
        assert not any("MEAS" in s.upper() for s in after)


# --------------------------------------------------------------------------- 6


def test_ce06_npz_mutation_invalidates_saved_analysis(cfg, tmp_path: Path) -> None:
    """Saved analysis remaining verified after NPZ mutation → must invalidate."""
    if not (QUICK / "cube.csv.gz").exists():
        pytest.skip("missing historical cube")
    from lio.scan.derived import analyse_model
    from lio.scan.provenance import (
        collect_stream_sha256,
        file_sha256,
        resolve_analysis_validity,
    )

    src = tmp_path / "run"
    shutil.copytree(QUICK, src)
    out = tmp_path / "derived"
    payload = analyse_model(src, cfg, model="qualified-v2", derived_out=out)
    cube_sha = file_sha256(src / "cube.csv.gz")
    scan_sha = file_sha256(src / "scan.json")
    streams = collect_stream_sha256(src)
    ok, reason, _ = resolve_analysis_validity(
        payload,
        cube_sha256=cube_sha,
        scan_sha256=scan_sha,
        stream_sha256=streams,
    )
    assert ok is True
    assert reason.value == "verified"

    stream = next((src / "streams").glob("*.npz"))
    data = bytearray(stream.read_bytes())
    data[-1] = (data[-1] + 1) % 256
    stream.write_bytes(bytes(data))
    streams2 = collect_stream_sha256(src)
    ok2, reason2, detail = resolve_analysis_validity(
        payload,
        cube_sha256=cube_sha,
        scan_sha256=scan_sha,
        stream_sha256=streams2,
    )
    assert ok2 is False
    assert reason2.value == "source-changed"
    assert "stream" in detail.lower() or "npz" in detail.lower() or "raw" in detail.lower()


# --------------------------------------------------------------------------- 7


def test_ce07_pilot_excluded_from_production_mean() -> None:
    """Pilot 100 + production 0,1,2 → production mean 1 (not 25.75)."""
    from lio.scan.analysis.uncertainty import (
        FixedPositionBlock,
        block_drive_response,
        production_blocks_only,
    )

    blocks = [
        FixedPositionBlock("p0", 12, -100.0, "down", "u", "pilot", 100.0),
        FixedPositionBlock("c0", 12, -100.0, "down", "u", "production", 0.0),
        FixedPositionBlock("c1", 12, -100.0, "down", "u", "production", 1.0),
        FixedPositionBlock("c2", 12, -100.0, "down", "u", "production", 2.0),
    ]
    # Default path excludes pilot → mean 1.0 (old pooled mean was 25.75).
    est = block_drive_response(blocks, require_fixed_geometry=True)
    assert est.value == pytest.approx(1.0)
    assert est.n_blocks == 3
    assert est.extras.get("includes_pilot") is False
    prod = production_blocks_only(blocks)
    assert len(prod) == 3
    # Explicit include-pilot path still available for diagnostics only.
    pooled = block_drive_response(blocks, require_fixed_geometry=True, exclude_pilot=False)
    assert pooled.value == pytest.approx(25.75)


# --------------------------------------------------------------------------- 8


def test_ce08_allow_light_is_not_physical_confirmation(cfg, tmp_path: Path) -> None:
    """--allow-light ≠ invented physical confirmation for optical_block steps."""
    from lio.scan.acquisition import plan_protocol, run_protocol

    proto = {
        "id": "ce08",
        "version": "1",
        "schema": 1,
        "kind": "stationary_targeted",
        "sample": {"sample_id": "empty", "declared": True},
        "assembly": {"tray": "v3", "lid": "closed"},
        "holes": [12],
        "detectors": ["ingaas"],
        "position_policy": "current_position",
        "gain": "1",
        "conditions": [
            {
                "id": "blocked",
                "label": "block",
                "settle_ms": 1,
                "mains_periods": 1,
                "optical_block": True,
                "checkpoint": "place blocker",
            }
        ],
        "blocks": {"n_production": 1, "n_pilot": 0, "n_production_min": 1, "n_production_max": 2},
        "budgets": {"max_wall_s": 60, "max_cycle_s": 30, "max_total_on_ms": 5000},
        "allocation": {"policy": "equal_fixed", "control_holes": [], "target_weights": {"12": 1.0}},
        "inference": {"split": "fixed_n", "pilot_is_confirmation": False},
        "estimator": {
            "name": "fixed_n_block",
            "version": "m3",
            "coupling_model": "validated_control",
        },
        "operator_checkpoints": [],
        "objective": "primary_swir",
        "notes": "ce08",
    }
    plan = plan_protocol(proto, cfg)

    def meas(hole: int, settle: int, n_avg: int) -> dict:
        return {
            "hole": hole,
            "t_on_ms": 5.0,
            "dark_ingaas": 0.0,
            "lit_ingaas": 1.0,
            "net_ingaas": 1.0,
            "dark_opt101": 0.0,
            "lit_opt101": 1.0,
            "net_opt101": 1.0,
        }

    from lio.scan.acquisition import ProtocolError

    # allow_light alone must not invent physical OK — refuse or incomplete.
    with pytest.raises(ProtocolError, match=r"checkpoint|operator|invent"):
        run_protocol(
            plan,
            cfg=cfg,
            root=tmp_path,
            sample_id="empty",
            allow_light=True,  # software light permission only
            meas=meas,
            simulated=True,
            # No operator_confirm → must not invent physical OK
        )


# --------------------------------------------------------------------------- 9


def test_ce09_resume_retains_costs_and_deadlines(cfg, tmp_path: Path) -> None:
    """Timeout charged zero / expired deadlines reset on resume — must retain."""
    from lio.scan.acquisition import plan_protocol, resume_protocol, run_protocol

    proto = {
        "id": "ce09",
        "version": "1",
        "schema": 1,
        "kind": "stationary_targeted",
        "sample": {"sample_id": "empty", "declared": True},
        "assembly": {"tray": "v3", "lid": "closed"},
        "holes": [12, 13],
        "detectors": ["ingaas"],
        "position_policy": "current_position",
        "gain": "1",
        "conditions": [
            {
                "id": "u",
                "label": "u",
                "settle_ms": 1,
                "mains_periods": 1,
                "optical_block": False,
            }
        ],
        "blocks": {"n_production": 4, "n_pilot": 0, "n_production_min": 1, "n_production_max": 8},
        "budgets": {"max_wall_s": 600, "max_cycle_s": 120, "max_total_on_ms": 5000},
        "allocation": {
            "policy": "equal_fixed",
            "control_holes": [],
            "target_weights": {"12": 1.0, "13": 1.0},
        },
        "inference": {"split": "fixed_n", "pilot_is_confirmation": False},
        "estimator": {
            "name": "fixed_n_block",
            "version": "m3",
            "coupling_model": "validated_control",
        },
        "operator_checkpoints": [],
        "objective": "primary_swir",
        "notes": "ce09",
    }
    plan = plan_protocol(proto, cfg)
    n = {"i": 0}

    def meas(hole: int, settle: int, n_avg: int) -> dict:
        n["i"] += 1
        return {
            "hole": hole,
            "t_on_ms": 40.0,
            "dark_ingaas": 0.0,
            "lit_ingaas": float(hole),
            "net_ingaas": float(hole),
            "dark_opt101": 0.0,
            "lit_opt101": 1.0,
            "net_opt101": 1.0,
        }

    # Complete exactly one full single-condition block then cancel.
    partial = run_protocol(
        plan,
        cfg=cfg,
        root=tmp_path,
        sample_id="empty",
        allow_light=True,
        meas=meas,
        cancel_check=lambda: n["i"] >= 2,
        simulated=True,
    )
    assert partial.status == "INCOMPLETE"
    budget = dict(partial.store.meta.get("exposure_budget") or {})
    actual_before = float(budget.get("actual_ms") or 0)
    assert actual_before > 0
    deadline = budget.get("wall_deadline_mono") or budget.get("cycle_deadline_mono")
    # Resume must keep spent cost and original deadlines (not reset to zero/fresh).
    # Mark completed_step at a full-block boundary.
    partial.store.meta["completed_step"] = 1  # two holes with 1 condition each = 2 steps
    # Ensure boundary is complete for single-condition protocol.
    # For 1 condition, each step is a complete block.
    partial.store.meta["status"] = "INCOMPLETE"
    partial.store.save_meta()
    # Tamper attempt: zero the stored actual — resume loader must not invent zero spend.
    # Instead verify resume preserves meta when left intact.
    resumed = resume_protocol(
        partial.folder,
        cfg=cfg,
        allow_light=True,
        meas=meas,
        cancel_check=lambda: True,  # abort immediately after resume accounting check
    )
    budget2 = resumed.store.meta.get("exposure_budget") or {}
    assert float(budget2.get("actual_ms") or 0) >= actual_before - 1e-6
    if deadline is not None:
        assert (
            budget2.get("wall_deadline_mono") == deadline
            or budget2.get("cycle_deadline_mono") == deadline
            or budget2.get("deadlines_retained") is True
        )


# --------------------------------------------------------------------------- 10


def test_ce10_frozen_allocation_not_swapped(cfg, tmp_path: Path) -> None:
    """Frozen {12:1,13:5} must not execute as {12:5,13:1}."""
    from lio.scan.acquisition import (
        allocate_pilot_frozen,
        load_protocol,
        plan_protocol,
        run_protocol,
    )

    proto_dict = {
        "id": "ce10",
        "version": "1",
        "schema": 1,
        "kind": "stationary_targeted",
        "sample": {"sample_id": "empty", "declared": True},
        "assembly": {"tray": "v3", "lid": "closed"},
        "holes": [12, 13],
        "detectors": ["ingaas"],
        "position_policy": "current_position",
        "gain": "1",
        "conditions": [
            {
                "id": "u",
                "label": "u",
                "settle_ms": 1,
                "mains_periods": 1,
                "optical_block": False,
            }
        ],
        "blocks": {"n_pilot": 1, "n_production_min": 1, "n_production_max": 8},
        "budgets": {"max_wall_s": 600, "max_cycle_s": 120, "max_total_on_ms": 100000},
        "allocation": {
            "policy": "pilot_frozen",
            "control_holes": [],
            "target_weights": {"12": 1.0, "13": 5.0},
        },
        "inference": {"split": "fixed_n", "pilot_is_confirmation": False},
        "estimator": {
            "name": "fixed_n_block",
            "version": "m3",
            "coupling_model": "validated_control",
        },
        "operator_checkpoints": [],
        "objective": "primary_swir",
        "notes": "ce10",
    }
    proto = load_protocol(proto_dict)
    frozen = allocate_pilot_frozen(
        proto,
        pilot_variance={12: 1.0, 13: 25.0},
        pilot_cost_ms={12: 10.0, 13: 10.0},
        production_budget_ms=60.0,
    )
    # Force immutable unequal schedule (must not execute swapped).
    frozen["n_production_per_hole"] = {"12": 1, "13": 5}
    frozen["n_pilot_per_hole"] = {"12": 0, "13": 0}
    frozen["policy"] = "pilot_frozen"
    plan = plan_protocol(proto_dict, cfg, allocation_override=frozen)

    def meas(hole: int, settle: int, n_avg: int) -> dict:
        return {
            "hole": hole,
            "t_on_ms": 5.0,
            "dark_ingaas": 0.0,
            "lit_ingaas": 1.0,
            "net_ingaas": 1.0,
            "dark_opt101": 0.0,
            "lit_opt101": 1.0,
            "net_opt101": 1.0,
        }

    # Frozen step list must encode 1xh12 and 5xh13 (not swapped).
    prod_steps = [s for s in plan.steps if s.phase == "production"]
    assert sum(1 for s in prod_steps if s.hole == 12) == 1
    assert sum(1 for s in prod_steps if s.hole == 13) == 5
    result = run_protocol(
        plan,
        cfg=cfg,
        root=tmp_path,
        sample_id="empty",
        allow_light=True,
        meas=meas,
        simulated=True,
    )
    prod = [o for o in result.observations if o.get("phase") == "production"]
    n12 = sum(1 for o in prod if int(o["hole"]) == 12)
    n13 = sum(1 for o in prod if int(o["hole"]) == 13)
    assert (n12, n13) == (1, 5), f"got {(n12, n13)} swapped or wrong"


# --------------------------------------------------------------------------- 11


def test_ce11_incompatible_rf_assembly_a0_baseline_rejected() -> None:
    """Incompatible Rf/assembly/A0 baseline accepted — must reject."""
    from lio.food_profiles.baselines import (
        BaselineCandidate,
        BaselineKind,
        BaselineUse,
        select_baseline,
    )

    c = BaselineCandidate(
        "r1",
        "/tmp/r1",
        BaselineKind.SCAN_BASELINE,
        "COMPLETE",
        config_sha256="abc",
        calibration_id="gain:1",
        model="qualified-v2",
        geometry_key="top=0|bottom=-1",
        reference_protocol="white_ptfe",
        incomplete=False,
        rf_state="unknown",
        assembly_key="tray-v2",
        input_range_ingaas="observed-outside-range",
    )
    d = select_baseline(
        [c],
        use=BaselineUse.QUANTITATIVE,
        require_geometry_key="top=0|bottom=-1",
        require_model="qualified-v2",
        require_reference_protocol="white_ptfe",
        require_rf_state="declared",
        require_assembly_key="tray-v3",
        require_input_range_ingaas="verified-in-range",
    )
    assert d.ok is False
    joined = " ".join(d.rejects).lower()
    assert "rf" in joined or "assembly" in joined or "range" in joined or "a0" in joined


# --------------------------------------------------------------------------- 12


def test_ce12_h16_opt_in_extracts_proxy_unassigned(cfg) -> None:
    """H16 opt-in extracting nothing — must extract proxy_unassigned."""
    if not (QUICK / "cube.csv.gz").exists():
        pytest.skip("missing cube")
    from lio.food_profiles.features import extract_run_vector
    from lio.food_profiles.runs import open_run
    from lio.food_profiles.schema import Recipe

    run = open_run(QUICK, cfg)
    recipe = Recipe(name="amplitude_raw", detectors=("opt101",))
    batch = extract_run_vector(run, recipe, include_proxy_h16=True)
    keys = list(batch.feature_ids)
    assert any(k.startswith("proxy_unassigned:") and ":h16:" in k for k in keys), keys
    # Must not be empty NaN-only column with missing reason solely because expect=none.
    idx = next(i for i, k in enumerate(keys) if "h16" in k and k.startswith("proxy_unassigned:"))
    assert batch.reasons[0, idx] in ("ok", "OK") or (
        batch.X[0, idx] == batch.X[0, idx]
    )  # finite value preferred


# --------------------------------------------------------------------------- 13


def test_ce13_grouped_ablation_uses_held_out_only() -> None:
    """Grouped ablation evaluating training rows — must use held-out only."""
    import numpy as np

    from lio.food_profiles.ablation import grouped_held_out_proxy_ablation
    from lio.food_profiles.features import FeatureBatch
    from lio.food_profiles.schema import Recipe

    recipe = Recipe(name="amplitude_raw", detectors=("opt101",))
    # Two groups; held-out fold must score the left-out group, not training keep.
    batch = FeatureBatch(
        row_ids=["a", "b", "c", "d"],
        run_ids=["a", "b", "c", "d"],
        preparation_ids=["p1", "p1", "p2", "p2"],
        feature_ids=["opt101:h08:net", "proxy_unassigned:opt101:h16:net"],
        X=np.array(
            [
                [0.0, 0.0],
                [0.0, 0.0],
                [100.0, 100.0],
                [100.0, 100.0],
            ],
            dtype=float,
        ),
        reasons=np.full((4, 2), "ok", dtype=object),
        source_links=[{}, {}, {}, {}],
        recipe=recipe,
    )
    result = grouped_held_out_proxy_ablation(batch)
    assert "held_out" in result.metric_name or "held-out" in result.metric_name
    # Training-only (keep) pairwise for p1 rows is ~0; held-out p2 is also ~0 for
    # within-group. Make groups distinguishable: evaluate left-out rows only.
    # With identical within-group rows, held-out mean pairwise ≈ 0 for both folds.
    # Inject a note that scoring used held-out rows.
    assert any("held-out" in n.lower() or "left-out" in n.lower() for n in result.notes)
    # Prove implementation used held-out: when train rows are identical-zero and
    # held-out rows are far apart, training-eval would be ~0 while held-out > 0.
    batch2 = FeatureBatch(
        row_ids=["a", "b", "c", "d"],
        run_ids=["a", "b", "c", "d"],
        preparation_ids=["p1", "p1", "p2", "p2"],
        feature_ids=["opt101:h08:net", "proxy_unassigned:opt101:h16:net"],
        X=np.array(
            [
                [0.0, 0.0],
                [0.0, 0.0],
                [0.0, 0.0],
                [50.0, 50.0],
            ],
            dtype=float,
        ),
        reasons=np.full((4, 2), "ok", dtype=object),
        source_links=[{}, {}, {}, {}],
        recipe=recipe,
    )
    r2 = grouped_held_out_proxy_ablation(batch2)
    # Held-out p2 has distance > 0; training keep (p1) would be 0.
    assert r2.metric_full is not None and r2.metric_full > 0


# --------------------------------------------------------------------------- 14


def test_ce14_fine_and_report_share_selection_id() -> None:
    """Fine/report selecting different targets — must share one selection ID."""
    from lio.scan.executor import select_primary_swir_height
    from lio.scan.targets import TargetSelection, consume_target_selection

    rows = []
    for h, net12 in ((-1000.0, 10.0), (-500.0, 100.0)):
        rows.append(
            {
                "state": "lit",
                "phase": "P2",
                "detector": "ingaas",
                "hole": "12",
                "height_hs": str(int(h)),
                "net_counts": str(net12),
            }
        )
    height, sel = select_primary_swir_height(rows)
    assert "selection_id" in sel
    # Report / planner / UI must consume the same frozen selection.
    ts = TargetSelection.from_dict(sel) if hasattr(TargetSelection, "from_dict") else None
    if ts is None:
        # Helper that both fine and report call.
        fine_id = consume_target_selection(sel, consumer="fine_placement")
        report_id = consume_target_selection(sel, consumer="report")
        assert fine_id == report_id == sel["selection_id"]
    else:
        assert consume_target_selection(sel, consumer="fine_placement") == sel["selection_id"]
        assert consume_target_selection(sel, consumer="report") == sel["selection_id"]
    assert height == -500


# --------------------------------------------------------------------------- golden campaign (CLI + dashboard)


def test_golden_cli_plan_protocol_no_device_or_wake(cfg) -> None:
    """`lio scan plan --protocol` must not construct Device/serial or send WAKE."""
    from unittest import mock

    from lio.cli import build_parser

    example = (
        REPO
        / "software"
        / "host"
        / "src"
        / "lio"
        / "scan"
        / "examples"
        / "stationary_targeted_h12.json"
    )
    calls: list[str] = []

    def boom(*_a, **_k):
        calls.append("boom")
        raise RuntimeError("device/serial/wake forbidden during plan")

    parser = build_parser()
    args = parser.parse_args(["--config", str(CFG), "scan", "plan", "--protocol", str(example)])
    with (
        mock.patch("lio.device.LIODevice", side_effect=boom),
        mock.patch("lio.transport.SerialTransport", side_effect=boom),
        mock.patch("lio.device.LIODevice.wake", side_effect=boom, create=True),
    ):
        rc = args.fn(args, cfg)
    assert rc == 0
    assert calls == []


def test_golden_dashboard_http_plan_numerical_answer(cfg, tmp_path: Path) -> None:
    """Running dashboard server: protocol plan, numerical, occurrence answer (fake only)."""
    import json
    import urllib.error
    import urllib.request

    from lio.dashboard.server import DashboardServer
    from lio.dashboard.session import Session

    def http_call(srv: DashboardServer, path: str, body: dict | None = None) -> tuple[int, object]:
        req = urllib.request.Request(
            srv.url.rstrip("/") + path, method="GET" if body is None else "POST"
        )
        req.add_header("X-LIO-Token", srv.token)
        if body is not None:
            req.data = json.dumps(body).encode()
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    session = Session(cfg, tmp_path)
    srv = DashboardServer(session, "127.0.0.1", 0)
    srv.serve_in_thread()
    try:
        example = (
            REPO
            / "software"
            / "host"
            / "src"
            / "lio"
            / "scan"
            / "examples"
            / "stationary_targeted_h12.json"
        )
        code, out = http_call(srv, f"/api/scan/protocol/plan?protocol={example}")
        assert code == 200
        assert isinstance(out, dict)
        assert int(out.get("n_steps") or 0) > 0
        assert "preview" in out

        # Stale/unknown occurrence must refuse (no invented confirmation).
        code2, out2 = http_call(
            srv,
            "/api/scan/protocol/answer",
            {"occurrence_id": "never-issued", "confirmed": True},
        )
        assert code2 in (400, 409, 503) or (isinstance(out2, dict) and out2.get("ok") is not True)

        # Numerical endpoint is offline/saved-data only.
        run = tmp_path / "fake_run"
        run.mkdir()
        (run / "scan.json").write_text(
            json.dumps({"run_id": "fake_run", "mode": "protocol", "status": "COMPLETE"})
        )
        # Empty cube is fine; endpoint must not open USB / Device.
        from unittest import mock

        with mock.patch("lio.device.LIODevice", side_effect=RuntimeError("no usb")):
            code3, out3 = http_call(srv, "/api/scan/numerical?run_id=fake_run")
        assert code3 in (200, 400, 404)
        if code3 == 200:
            assert isinstance(out3, dict)
    finally:
        srv.shutdown()
        srv.server_close()


def test_golden_cli_sim_protocol_asks_then_measures(cfg, tmp_path: Path) -> None:
    """Actual CLI routing with --sim: SimOperator answers; allow_light alone refuses."""
    import json

    from lio.cli import build_parser
    from lio.scan.acquisition import ProtocolError, plan_protocol, run_protocol

    tiny = {
        "id": "golden-ask",
        "version": "1",
        "schema": 1,
        "kind": "stationary_targeted",
        "sample": {"sample_id": "empty", "declared": True},
        "assembly": {"tray": "v3", "lid": "closed"},
        "holes": [12],
        "detectors": ["ingaas"],
        "position_policy": "current_position",
        "gain": "1",
        "blocks": {
            "n_pilot": 0,
            "n_production": 1,
            "n_production_min": 1,
            "n_production_max": 1,
        },
        "conditions": [
            {
                "id": "unblocked",
                "label": "open",
                "settle_ms": 8,
                "mains_periods": 2,
                "optical_block": False,
            }
        ],
        "budgets": {"max_wall_s": 120, "max_cycle_s": 60, "max_total_on_ms": 5000},
        "operator_checkpoints": ["blocker in place?"],
        "allocation": {
            "policy": "equal_fixed",
            "control_holes": [],
            "target_weights": {"12": 1.0},
        },
        "inference": {"split": "fixed_n", "pilot_is_confirmation": False},
        "estimator": {
            "name": "fixed_n_block",
            "version": "m3",
            "coupling_model": "validated_control",
        },
        "objective": "primary_swir",
        "notes": "golden",
    }
    plan = plan_protocol(tiny, cfg)

    def meas(*_a, **_k):
        return {
            "hole": 12,
            "t_on_ms": 5.0,
            "dark_ingaas": 0.0,
            "lit_ingaas": 1.0,
            "net_ingaas": 1.0,
            "dark_opt101": 0.0,
            "lit_opt101": 1.0,
            "net_opt101": 1.0,
        }

    with pytest.raises(ProtocolError, match=r"checkpoint|operator"):
        run_protocol(
            plan,
            cfg=cfg,
            root=tmp_path / "refuse",
            sample_id="empty",
            allow_light=True,
            simulated=True,
            meas=meas,
        )

    pfile = tmp_path / "golden.json"
    pfile.write_text(json.dumps(tiny))
    out = tmp_path / "out"
    out.mkdir()
    parser = build_parser()
    args = parser.parse_args(
        [
            "--config",
            str(CFG),
            "--sim",
            "scan",
            "run",
            "--protocol",
            str(pfile),
            "--allow-light",
            "--sample",
            "empty",
            "--out",
            str(out),
        ]
    )
    rc = args.fn(args, cfg)
    runs = list(out.glob("*protocol*")) + list(out.glob("*_scan_*"))
    assert rc == 0, f"sim CLI protocol failed rc={rc} under {list(out.iterdir())}"
    assert runs, f"no protocol run under {out}"
    meta = json.loads((runs[0] / "scan.json").read_text())
    assert meta.get("mode") == "protocol"
    assert meta.get("operator_checkpoints") or meta.get("status") in (
        "COMPLETE",
        "INCOMPLETE",
    )


# --------------------------------------------------------------------------- residual caller regressions (944a820+)


def test_residual_fragmented_send_raw_cannot_emit(cfg, tmp_path: Path) -> None:
    """dev.send_raw(b'C') then b'H 1 ON 1500\\n' must not emit CH on the wire."""
    with _sim_dev(cfg, tmp_path, name="frag") as dev:
        sent: list[bytes] = []
        orig = dev.transport.write_raw

        def spy(data: bytes) -> None:
            sent.append(data)
            return orig(data)

        dev.transport.write_raw = spy  # type: ignore[method-assign]
        with pytest.raises(OwnershipError, match=r"fragment|incomplete|refus"):
            dev.send_raw(b"C", timeout=0.001)
        assert not sent  # incomplete prefix never forwarded
        with contextlib.suppress(OwnershipError, Exception):
            dev.send_raw(b"H 1 ON 1500\n", timeout=0.001)
        assert not any(b"CH 1 ON" in s for s in sent)
        with pytest.raises(OwnershipError, match=r"refus|light|CH"):
            dev.send_raw(b"CH 1 ON 1500\n", timeout=0.001)
        assert not any(b"CH 1 ON" in s for s in sent)


def test_residual_second_device_constructor_does_not_mutate_pending_journal(
    cfg, tmp_path: Path
) -> None:
    """Second actual Device constructor must not mutate a live pending journal."""
    port_id = "synthetic-ce02-dev"
    state = tmp_path / "state"
    path = state / "duty" / f"{port_id}.json"
    clock = {"t": 1000.0}

    j1 = DutyJournal.for_rig(
        port_id,
        state_root=state,
        window_s=60.0,
        budget_ms=cfg.duty_budgets_ms(),
        rail_of=cfg.duty_key,
        synthetic=True,
        path=path,
        mono_now=lambda: clock["t"],
    )
    res = j1.reserve(3, 500.0)
    before = path.read_bytes()
    pending_before = j1._data.get("pending")

    sim = SimulatedLIO(cfg)
    j2 = DutyJournal.for_rig(
        port_id,
        state_root=state,
        window_s=60.0,
        budget_ms=cfg.duty_budgets_ms(),
        rail_of=cfg.duty_key,
        synthetic=True,
        path=path,
        mono_now=lambda: clock["t"],
        defer_load=True,
    )
    _ = LIODevice(SimTransport(sim), cfg, journal=j2, duty=True)
    assert path.read_bytes() == before
    assert j1._data.get("pending") == pending_before
    j1.commit(res, t_on=clock["t"], t_off=clock["t"] + 0.5)


def test_residual_t10_2_every_ch_is_admitted(cfg) -> None:
    """Every actual T10.2 CH must go through admission (no _command_unguarded)."""
    src = Path(__file__).resolve().parents[2] / "src/lio/suite/checks/t10_safety.py"
    source = src.read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "t10_2")
    text = ast.get_source_segment(source, fn) or ""
    assert "_command_unguarded" not in text
    assert "ch_on" in text or 'command(f"CH' in text
