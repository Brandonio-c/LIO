"""M5 scout/confirm shared objective."""

from __future__ import annotations

import pytest

from lio.scan.targets import (
    apply_confirm_perturbation,
    freeze_confirm_plan,
    h16_proxy_diagnostic_objective,
    primary_swir_objective,
    scout_height,
)

pytestmark = pytest.mark.unit


def test_blind_noise_h16_cannot_change_primary_swir_optimum() -> None:
    heights = [-1000.0, -2000.0, -3000.0]
    # Clean primary-SWIR responses: best at -2000.
    base = {
        -1000.0: {12: 5.0, 13: 1.0, 14: 1.0, 15: 1.0},
        -2000.0: {12: 20.0, 13: 2.0, 14: 2.0, 15: 2.0},
        -3000.0: {12: 8.0, 13: 1.0, 14: 1.0, 15: 1.0},
    }
    # Contaminate with extreme blind / noise / h16 residual.
    dirty = {
        h: {
            **resp,
            1: 1e6,  # structural blind-ish noise
            10: 1e6,
            16: 1e9,  # h16 must not steer primary-SWIR
        }
        for h, resp in base.items()
    }
    # Make -1000 look best if h16 were included.
    dirty[-1000.0][16] = 1e12
    clean = scout_height(heights, base, objective=primary_swir_objective())
    messy = scout_height(
        heights, dirty, objective=primary_swir_objective(), structural_blinds=[1, 10]
    )
    assert clean.status == "selected"
    assert messy.status == "selected"
    assert clean.frozen_height_hs == messy.frozen_height_hs == -2000.0


def test_scout_confirm_disjoint_and_perturb_confirm() -> None:
    heights = [0.0, 1000.0]
    responses = {
        0.0: {12: 1.0, 13: 1.0, 14: 1.0, 15: 1.0},
        1000.0: {12: 10.0, 13: 2.0, 14: 2.0, 15: 2.0},
    }
    scout = scout_height(heights, responses)
    plan = freeze_confirm_plan(scout, n_confirm_blocks=3, scout_block_ids=["scout-a"])
    assert set(plan.scout_block_ids).isdisjoint(plan.confirm_block_ids)
    assert plan.frozen_height_hs == 1000.0
    again = apply_confirm_perturbation(plan, {"confirm-0": 999.0, "confirm-1": -50.0})
    assert again.frozen_height_hs == plan.frozen_height_hs


def test_flat_and_missing_explicit() -> None:
    heights = [0.0, 1.0]
    flat = {0.0: {12: 1.0}, 1.0: {12: 1.0}}
    r = scout_height(heights, flat, objective=primary_swir_objective(), flat_eps=0.1)
    assert r.status in ("flat", "selected")  # equal scores → flat
    if abs(1.0 - 1.0) <= 0.1:
        assert r.status == "flat"
        assert r.frozen_height_hs is None
    empty = scout_height(heights, {0.0: {}, 1.0: {}})
    assert empty.status == "missing_target"
    assert empty.frozen_height_hs is None


def test_h16_proxy_is_separate_objective() -> None:
    obj = h16_proxy_diagnostic_objective()
    assert obj.target_holes == (16,)
    assert "primary" not in obj.name or "proxy" in obj.name
    heights = [0.0, 1.0]
    r = scout_height(
        heights,
        {0.0: {16: 10.0}, 1.0: {16: 50.0}},
        objective=obj,
    )
    assert r.status == "selected"
    assert r.frozen_height_hs == 1.0
