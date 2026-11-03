from __future__ import annotations

import math

import pytest

from lio import analysis as A

pytestmark = pytest.mark.unit


class TestStats:
    def test_basic(self) -> None:
        s = A.stats([1.0, 2.0, 3.0, 4.0])
        assert s.n == 4 and s.mean == 2.5
        assert s.std == pytest.approx(math.sqrt(5 / 3))
        assert (s.min, s.max) == (1.0, 4.0)
        assert s.cv == pytest.approx(s.std / 2.5)

    def test_single_value(self) -> None:
        s = A.stats([7.0])
        assert s.std == 0.0 and s.cv == 0.0

    def test_zero_mean_cv_is_inf(self) -> None:
        assert A.stats([-1.0, 1.0]).cv == math.inf

    def test_empty(self) -> None:
        with pytest.raises(ValueError):
            A.stats([])


class TestPercentile:
    def test_interpolates(self) -> None:
        v = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert A.percentile(v, 50) == 3.0
        assert A.percentile(v, 0) == 1.0
        assert A.percentile(v, 100) == 5.0
        assert A.percentile(v, 99) == pytest.approx(4.96)

    def test_errors(self) -> None:
        with pytest.raises(ValueError):
            A.percentile([], 50)
        with pytest.raises(ValueError):
            A.percentile([1.0], 101)


class TestSlope:
    def test_exact_line(self) -> None:
        assert A.linear_slope([0, 1, 2, 3], [1, 3, 5, 7]) == pytest.approx(2.0)

    def test_flat_time(self) -> None:
        assert A.linear_slope([1, 1], [0, 5]) == 0.0

    def test_errors(self) -> None:
        with pytest.raises(ValueError):
            A.linear_slope([1], [1])
        with pytest.raises(ValueError):
            A.linear_slope([1, 2], [1])


THR = {"detect_sigma": 10, "detect_min": 50, "weak_sigma": 3, "weak_min": 15}


class TestDetection:
    @pytest.mark.parametrize(
        ("net", "sigma", "level"),
        [
            (5000, 3, "signal"),
            (50, 3, "signal"),  # min_counts floor
            (49, 3, "weak"),
            (15, 3, "weak"),
            (14, 3, "none"),
            (90, 10, "weak"),  # 10 sigma = 100 > 90
            (-500, 3, "none"),
        ],
    )
    def test_levels(self, net: float, sigma: float, level: str) -> None:
        d = A.detect_level(net, sigma, **THR)
        assert d.level == level
        assert d.signal_threshold == max(10 * sigma, 50)


def _det(level: str) -> A.Detection:
    return A.Detection(level, 0, 1, 50, 15)


class TestJudge:
    @pytest.mark.parametrize(
        ("expect", "observed", "never_fail", "status"),
        [
            ("signal", "signal", False, "PASS"),
            ("signal", "weak", False, "WARN"),
            ("signal", "none", False, "FAIL"),
            ("signal", "none", True, "WARN"),
            ("weak", "signal", False, "PASS"),
            ("weak", "weak", False, "PASS"),
            ("weak", "none", False, "WARN"),
            ("none", "none", False, "PASS"),
            ("none", "signal", False, "FAIL"),
            ("none", "weak", True, "WARN"),
        ],
    )
    def test_matrix(self, expect: str, observed: str, never_fail: bool, status: str) -> None:
        v = A.judge_expectation(expect, _det(observed), never_fail_absence=never_fail)
        assert v.status == status and v.reason


class TestChecks:
    def test_polarity(self) -> None:
        assert A.polarity_reversed(-100, 4, -5)
        assert not A.polarity_reversed(-10, 4, -5)
        assert A.polarity_reversed(-6, 0.1, -5)  # sigma floor of 1 count

    def test_saturated(self) -> None:
        assert A.saturated(27000, 27000) and not A.saturated(26999, 27000)

    def test_off_returned(self) -> None:
        assert A.off_returned(205, 200, 2.5, 5)
        assert not A.off_returned(230, 200, 2.5, 5)
        assert A.off_returned(203, 200, 0.0, 5)  # sigma floor of 1 count


class TestSignatures:
    def test_cosine(self) -> None:
        assert A.cosine([1, 0], [1, 0]) == pytest.approx(1.0)
        assert A.cosine([1, 0], [0, 1]) == pytest.approx(0.0)
        assert A.cosine([0, 0], [1, 1]) == 0.0

    def test_duplicates_found(self) -> None:
        sigs = {
            1: (2000.0, 5.0),
            2: (2010.0, 4.0),  # same as 1
            3: (1000.0, 0.0),  # same direction, different amplitude
            8: (4000.0, 2000.0),
            13: (0.0, 3800.0),
            16: (2.0, 3.0),  # too small to compare
        }
        groups = A.duplicate_signatures(sigs, similarity=0.98, min_total=200)
        assert groups == [[1, 2]]

    def test_no_duplicates(self) -> None:
        sigs = {3: (2400.0, 0.0), 8: (4500.0, 2000.0), 13: (0.0, 3800.0)}
        assert A.duplicate_signatures(sigs, similarity=0.98, min_total=200) == []

    def test_chain_of_duplicates(self) -> None:
        sigs = {h: (1500.0 + h, 0.0) for h in (1, 2, 3, 4, 5)}
        assert A.duplicate_signatures(sigs, similarity=0.98, min_total=200) == [[1, 2, 3, 4, 5]]


def _step(n_pre: int, n_on: int, n_post: int, dt_us: int, tau_ms: float, step: float):
    t = [i * dt_us for i in range(n_pre + n_on + n_post)]
    t_on = (t[n_pre - 1] + t[n_pre]) / 2
    raw = []
    for i, ti in enumerate(t):
        if n_pre <= i < n_pre + n_on:
            frac = 1 - math.exp(-(ti - t_on) / 1000.0 / tau_ms) if tau_ms > 0 else 1.0
            raw.append(round(100 + step * frac))
        else:
            raw.append(100)
    return t, raw


class TestSettling:
    def test_fast_settles_in_first_sample(self) -> None:
        t, raw = _step(4, 24, 12, 1400, 0.01, 3000)
        s = A.settling(t, raw, 4, 28, fraction=0.99)
        assert s.within_first_sample
        assert s.step == pytest.approx(3000, rel=0.01)
        assert s.t_settle_ms == pytest.approx(0.7, abs=0.01)
        assert s.upper_bound_ms == s.t_settle_ms
        assert s.tau_ms is None

    def test_slow_settle_fits_tau(self) -> None:
        t, raw = _step(4, 40, 4, 1400, 15.0, 3000)
        s = A.settling(t, raw, 4, 44, fraction=0.99)
        assert not s.within_first_sample
        assert s.tau_ms == pytest.approx(15.0, rel=0.15)
        assert s.plateau == pytest.approx(3100, rel=0.02)  # recovered although not yet flat
        assert s.t_settle_ms == pytest.approx(15.0 * math.log(100), rel=0.15)

    def test_unfittable_reports_observed(self) -> None:
        # irregular sample spacing: no model fit, fall back to the observed time
        t = [0, 1000, 2000, 3000, 9000, 9500, 20000, 21000]
        raw = [100, 100, 100, 100, 1500, 2600, 3100, 3100]
        s = A.settling(t, raw, 4, 8, fraction=0.99)
        assert s.tau_ms is None and not s.within_first_sample
        assert s.t_settle_ms == pytest.approx((20000 - 6000) / 1000)

    def test_too_few_lit_samples_falls_back(self) -> None:
        t, raw = _step(4, 3, 0, 1400, 5.0, 3000)
        s = A.settling(t, raw, 4, 7, fraction=0.99)
        assert s.tau_ms is None

    def test_noisy_flat_plateau_is_no_fit(self) -> None:
        t = [i * 1400 for i in range(12)]
        raw = [100] * 4 + [3000, 3200, 2900, 3150, 2950, 3100, 3050, 3000]
        s = A.settling(t, raw, 4, 12, fraction=0.99)
        assert s.tau_ms is None

    def test_bad_indices(self) -> None:
        with pytest.raises(ValueError):
            A.settling([0, 1], [1, 2], 0, 1, fraction=0.99)

    def test_recommend(self) -> None:
        assert A.recommend_settle_ms([0.7, 2.1, 1.0], 1.5) == 4
        assert A.recommend_settle_ms([0.1], 1.5) == 1
        with pytest.raises(ValueError):
            A.recommend_settle_ms([], 1.5)

    def test_zero_step_counts_as_settled(self) -> None:
        t, raw = _step(4, 10, 2, 1400, 1.0, 0)
        s = A.settling(t, raw, 4, 14, fraction=0.99)
        assert s.within_first_sample and s.tau_ms is None
