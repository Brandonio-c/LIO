"""Versioned manifests, validity reasons, recipes and feature identities."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from lio.food_profiles import SCHEMA_VERSION

DETECTORS = ("opt101", "ingaas")
BROADBAND_LABELS = frozenset({"white", "pink"})

# Default stationary food optical selection (plan §4.1).
DEFAULT_SELECTION = {
    "state": "lit",
    "phase": "P2",
    "direction": "down",
    "rep": 0,
    "kind": "measure",
}


class CellReason(str, Enum):
    OK = "ok"
    BLIND = "blind"
    WEAK_EXCLUDED = "weak_excluded"
    MISSING = "missing"
    SATURATED = "saturated"
    NONFINITE = "nonfinite"
    UNSUPPORTED_HEIGHT = "unsupported_height"
    UNVERIFIED_MAP = "unverified_map"
    INCOMPATIBLE_REFERENCE = "incompatible_reference"
    WEAK_DENOMINATOR = "weak_denominator"
    INSUFFICIENT_ANALYSIS = "insufficient_analysis"
    EXCLUDED = "excluded"
    ZERO_VECTOR = "zero_vector"
    FLAT_PROFILE = "flat_profile"
    PROJECTION_NOT_SUPPORTED = "projection_not_supported"
    INDEPENDENCE_UNKNOWN = "independence_unknown"
    GROUP_METADATA_INSUFFICIENT = "group_metadata_insufficient"
    DESIGN_UNSUPPORTED = "design_unsupported"


@dataclass(frozen=True)
class FeatureId:
    detector: str
    hole: int
    kind: str = "net"  # net | o_envelope | curve_summary | ratio
    height_hs: float | None = None
    recipe: str | None = None

    @property
    def key(self) -> str:
        base = f"{self.detector}:h{self.hole:02d}:{self.kind}"
        if self.height_hs is not None:
            base += f":h{self.height_hs:g}"
        if self.recipe:
            base += f":{self.recipe}"
        return base


@dataclass
class Recipe:
    """Frozen processing recipe (validated small schema, not arbitrary code)."""

    name: str
    schema: int = SCHEMA_VERSION
    selection: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_SELECTION))
    representation: str = "amplitude"  # amplitude | shape | reference_relative | o_envelope
    height_policy: str = "exact_common"  # exact_common | interpolate | o_envelope
    max_gap_hs: float = 5000.0
    channel_policy: str = "expect_signal_or_weak"
    coupling_policy: str = "none"  # none | analysis_c | unavailable_if_missing
    reference_protocol: str = "none"  # none | explicit | prior_compatible
    vector_norm: bool = False
    snv: bool = False
    msc: bool = False
    scale: str = "none"  # none | mean_center | autoscaling | block
    aggregation: str = "preparation_mean"  # preparation_mean | run_level
    detectors: tuple[str, ...] = DETECTORS
    min_reference_denom: float = 5.0
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["detectors"] = list(self.detectors)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Recipe:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        kwargs = {k: v for k, v in data.items() if k in known}
        if "detectors" in kwargs:
            kwargs["detectors"] = tuple(kwargs["detectors"])
        return cls(**kwargs)


# Built-in recipes (names are stable IDs).
BUILTIN_RECIPES: dict[str, Recipe] = {
    "amplitude_raw": Recipe(name="amplitude_raw", representation="amplitude"),
    "amplitude_shape_snv": Recipe(
        name="amplitude_shape_snv", representation="shape", snv=True, vector_norm=False
    ),
    "amplitude_vector_norm": Recipe(
        name="amplitude_vector_norm", representation="shape", vector_norm=True
    ),
    "amplitude_msc": Recipe(name="amplitude_msc", representation="shape", msc=True),
    "reference_relative": Recipe(
        name="reference_relative",
        representation="reference_relative",
        reference_protocol="explicit",
        coupling_policy="analysis_c",
    ),
    "o_envelope": Recipe(
        name="o_envelope", representation="o_envelope", height_policy="o_envelope"
    ),
}


def finite_json(value: Any) -> Any:
    """JSON-safe: NaN/Inf → null; numpy scalars → Python."""
    import math

    import numpy as np

    if value is None:
        return None
    if isinstance(value, (np.floating, float)):
        x = float(value)
        return None if not math.isfinite(x) else x
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, np.ndarray):
        return [finite_json(v) for v in value.tolist()]
    if isinstance(value, dict):
        return {str(k): finite_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite_json(v) for v in value]
    if isinstance(value, Enum):
        return value.value
    return value
