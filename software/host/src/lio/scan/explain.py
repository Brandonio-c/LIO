"""Explanations (plan §7): a flagged finding -> likely cause, parts, next manual check.

A rule table, first match wins. Patterns match the finding id (``*`` is one path
segment, ``hNN`` any hole); ``when`` can look at the finding's data and at the other
findings of the run, so one symptom can point to different causes in context (a
flat InGaAs curve with the dark pulled negative is a disconnected photodiode; with a
normal dark it is coupling).
"""

from __future__ import annotations

import fnmatch
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from lio.results import Status
from lio.scan.analysis.data import Finding


@dataclass(frozen=True)
class Explanation:
    cause: str
    parts: tuple[str, ...]
    check: str

    def to_dict(self) -> dict[str, Any]:
        return {"cause": self.cause, "parts": list(self.parts), "check": self.check}


Ctx = dict[str, Finding]
When = Callable[[Finding, Ctx], bool]


@dataclass(frozen=True)
class Rule:
    pattern: str
    explanation: Explanation
    when: When | None = None


def _status(ctx: Ctx, fid: str, *bad: Status) -> bool:
    f = ctx.get(fid)
    return f is not None and f.status in (bad or (Status.WARN, Status.FAIL))


def _dark_negative(det: str) -> When:
    def w(_: Finding, ctx: Ctx) -> bool:
        f = ctx.get(f"elec/{det}/dark_offset")
        return f is not None and f.value is not None and f.value < 0 and f.status == Status.FAIL

    return w


def _hole(f: Finding) -> str:
    for p in f.id.split("/"):
        if len(p) == 3 and p[0] == "h" and p[1:].isdigit():
            return str(int(p[1:]))
    return "n"


E = Explanation
RULES: tuple[Rule, ...] = (
    # ----------------------------------------------------------- link, ADC, run
    Rule(
        "system/link",
        E(
            "The board reset or stopped answering during the run (brown-out on the 5 V rail when "
            "the motors or LEDs draw current, a loose USB cable, or a firmware fault). Steps may "
            "have been lost while it was down.",
            ("Nano R4", "USB cable", "5 V supply", "ULN2003 boards"),
            "Re-seat the USB cable; watch for '# BOOT' while jogging both motors; raise the top to "
            "its upper end and set the top again before the next scan.",
        ),
    ),
    Rule(
        "system/adc",
        E(
            "The ADS1115 stopped answering on the software I²C bus mid-run.",
            ("ADS1115", "D11/D12 SDA/SCL wiring", "I²C pull-ups", "3.3/5 V supply"),
            "Run T03 (lio selftest --modules adc); check the SDA/SCL joints and the pull-ups.",
        ),
    ),
    Rule(
        "system/stage",
        E(
            "The tracked position is no longer trusted (an unexpected reset) or a move hit a soft "
            "limit.",
            ("lio.stage", "M1", "M2"),
            "Raise the top to its upper end by hand or jog, then 'lio stage set-top'.",
        ),
    ),
    Rule(
        "system/rail/*",
        E(
            "No hole on this rail gives light: the driver is not enabled, the rail supply is "
            "missing, or CE is not reaching the driver.",
            ("DRV1/DRV2", "CE1/CE2 line", "rail supply"),
            "Run T05.1 and T05.6 (rail current with the meter in series).",
        ),
    ),
    Rule(
        "system/interlocks",
        E(
            "A firmware interlock re-check failed at the end of the run: light was accepted while "
            "a motor moved, or CE with two holes selected.",
            ("firmware",),
            "Do not use the rig; run T10 and report the firmware version.",
        ),
    ),
    Rule(
        "system/duty",
        E(
            "An LED exceeded its on-time budget.",
            ("duty tracker", "firmware watchdog"),
            "Check the duty log in scan.json; run T10.",
        ),
    ),
    Rule(
        "system/addressing",
        E(
            "Two holes give the same response at every height: the same LED is lit for both (a "
            "stuck or doubled select bit in the shift registers, or two gates tied).",
            ("U1", "U2", "Q gates"),
            "Run T04 and T05.3 (isolation); look for a solder bridge.",
        ),
    ),
    Rule(
        "system/run",
        E(
            "The run did not complete: metrics needing the missing steps are SKIP.",
            ("run",),
            "See the abort reason; 'lio scan resume <run>' carries on from the next step.",
        ),
    ),
    # ----------------------------------------------------------- optics, per hole
    Rule(
        "optics/ingaas/hNN/response",
        E(
            "No light reaches the InGaAs from this hole, and the other InGaAs holes are flat too: "
            "the signal is electrical, not light. The photodiode is not connected to the "
            "amplifier (the 15 Nov signature).",
            ("D1", "U5", "SUM", "TIA_REF"),
            "Fault tree 'InGaAs coupling': meter the D1 leads and the pin 2/3 wiring of U5.",
        ),
        when=lambda f, c: _status(c, "optics/ingaas/electrical_only", Status.FAIL),
    ),
    Rule(
        "optics/*/hNN/response",
        E(
            "This hole gives no (or little) height-dependent light on a detector that should see "
            "it: the LED is dead or reversed, its MOSFET is open, it is wired to the wrong rail, "
            "or it is an LED that this detector cannot see (swapped or wrong part).",
            ("LED", "Q (MOSFET)", "rail wiring"),
            "Phone-camera check of the hole while it is lit (lio ch N on); meter the Q gate and "
            "drain; compare with the rail map.",
        ),
    ),
    Rule(
        "optics/*/hNN/plausibility",
        E(
            "A detector responds, with a height-dependent (optical) signal, to a hole whose "
            "wavelength it cannot see: the LED in this hole is not the one in the channel map "
            "(swapped with another hole, or the wrong part).",
            ("LED",),
            "Camera check of that hole (visible or not); compare the LED marking with "
            "docs/OPTICAL_CHANNEL_MAP.md; look for the hole it was swapped with (a response "
            "missing elsewhere).",
        ),
    ),
    # ----------------------------------------------------------- optics, detector
    Rule(
        "optics/ingaas/electrical_only",
        E(
            "Every InGaAs hole is flat in height while the coupling is large: the InGaAs output "
            "follows the LED current, not light. The photodiode is not connected to the TIA.",
            ("D1", "U5", "SUM", "TIA_REF"),
            "Fault tree 'InGaAs coupling': meter D1's leads to U5 pins 2/3; check the TIA "
            "feedback (Rf, Cf).",
        ),
    ),
    Rule(
        "optics/opt101/electrical_only",
        E(
            "Every OPT101 hole is flat in height: the OPT101 is not seeing light (blocked, wrong "
            "pin used, or its photodiode pins open).",
            ("OPT101",),
            "Check the OPT101 wiring (pins 1-8) and that nothing covers its window.",
        ),
    ),
    Rule(
        "optics/*/throughput",
        E(
            "Every hole on this detector is weaker than expected while the shape vs height is "
            "normal: less light reaches the detector (a dirty or blocked window, misalignment, or "
            "a weaker sample).",
            ("detector window", "alignment", "sample"),
            "Inspect and clean the deck window over the detector; re-run with the white tile.",
        ),
    ),
    Rule(
        "optics/stray",
        E(
            "Light reaches the detectors without going via the sample (height-invariant): "
            "reflections inside the chamber or light leaking between holes.",
            ("chamber walls", "hole baffles"),
            "Repeat with the black cup; inspect for shiny surfaces and gaps between holes.",
        ),
    ),
    Rule(
        "optics/*/headroom",
        E(
            "The strongest reading is close to saturation.",
            ("TIA gain", "LED current"),
            "Expect saturation with brighter samples; consider a lower gain.",
        ),
    ),
    Rule(
        "optics/*/snr",
        E(
            "A hole's signal is close to the noise.",
            ("LED", "detector"),
            "See the noise metrics; compare with the baseline.",
        ),
    ),
    Rule(
        "optics/optimum",
        E(
            "The best height is at an end of the travel: the true optimum may lie beyond it.",
            ("geometry",),
            "Check the sample position.",
        ),
    ),
    Rule(
        "optics/*/effectiveness",
        E(
            "Response lower than the baseline of the same sample.",
            ("LEDs", "window", "alignment"),
            "See trend/compare for where the change sits.",
        ),
    ),
    # ----------------------------------------------------------- electrical
    Rule(
        "elec/ingaas/coupling",
        E(
            "The InGaAs output follows the LED current and its dark is pulled negative: the "
            "photodiode is not connected to the amplifier (the 15 Nov signature).",
            ("D1", "U5", "SUM", "TIA_REF"),
            "Fault tree 'InGaAs coupling' (meter D1 leads, pin 2/3 wiring).",
        ),
        when=_dark_negative("ingaas"),
    ),
    Rule(
        "elec/*/coupling",
        E(
            "The detector output changes when an LED is on even though it cannot see that light: "
            "electrical coupling from the LED drive (shared ground return, or capacitive pick-up).",
            ("GND star point", "SUM/TIA_REF routing", "LED drive wiring"),
            "Check that the TIA reference and the LED return do not share a thin ground path.",
        ),
    ),
    Rule(
        "elec/*/ground_shift",
        E(
            "The coupling scales with the rail current: LED current through a shared ground "
            "resistance shifts the detector's reference (ground shift).",
            ("GND star point", "TIA_REF", "rail returns"),
            "Measure the voltage between the TIA ground and the supply ground with RAIL B lit; "
            "run the LED returns straight to the supply.",
        ),
    ),
    Rule(
        "elec/ingaas/dark_offset",
        E(
            "The InGaAs dark output is outside its range: a current flows into the TIA input (a "
            "negative output means current into pin 2: leakage, or the photodiode connected "
            "the wrong way or not at all).",
            ("U5 pin-2 node", "D1", "Rf", "board cleanliness"),
            "Meter the pin-2 node to ground; clean flux off the board; check D1's orientation.",
        ),
    ),
    Rule(
        "elec/opt101/dark_offset",
        E(
            "The OPT101 dark output is outside its range.",
            ("OPT101", "its supply"),
            "Check the OPT101 supply and pins 1/2/5.",
        ),
    ),
    Rule(
        "elec/*/drift",
        E(
            "The dark level drifted during the run: changing leakage (humidity, temperature) or "
            "warm-up.",
            ("U5 pin-2 node", "temperature"),
            "Re-run after a 30 min warm-up; keep the lid closed; note the room temperature.",
        ),
    ),
    Rule(
        "elec/*/hum",
        E(
            "Mains hum on the detector output: a missing earth bond or leakage from a charger.",
            ("earth bond", "chargers", "GND"),
            "Check the earth bond (circuit GND to mains earth); unplug the laptop charger and "
            "repeat.",
        ),
    ),
    Rule(
        "elec/*/coil_emi",
        E(
            "The motor coils couple into the detector while they switch.",
            ("motor wiring", "ULN2003", "detector wiring"),
            "Route the motor cables away from the detector leads; twist the coil pairs.",
        ),
    ),
    Rule(
        "optics/hNN/intermittent",
        E(
            "This hole's readings jump on both detectors at the same moment: an electrical "
            "event (a joint opening for an instant, or an intermittent short), not light.",
            ("LED", "Q (MOSFET)", "solder joints", "breadboard contacts"),
            "Wiggle-test the LED and MOSFET leads while watching 'lio ch N on' readings; "
            "reflow or re-seat the joints.",
        ),
    ),
    Rule(
        "optics/wrong_rail/hNN",
        E(
            "The LED lights when only the other rail's driver is enabled: it is wired to the "
            "wrong rail (its return or anode on the other driver).",
            ("rail wiring", "LED", "DRV1/DRV2"),
            "Trace the LED's wiring to its driver against docs/OPTICAL_CHANNEL_MAP.md; meter "
            "the rail current with the hole lit (T05.6).",
        ),
    ),
    Rule(
        "elec/*/ce_only",
        E(
            "Enabling a driver with no LED selected moves the detector output: driver-enable "
            "coupling (CE line or driver supply into the detector ground).",
            ("DRV1/DRV2", "CE1/CE2 lines", "GND"),
            "Look for the CE lines and driver supply near the detector wiring.",
        ),
    ),
    Rule(
        "elec/*/hNN/select_only",
        E(
            "Selecting a MOSFET (gate drive, no LED current) moves the detector output: gate-drive "
            "coupling.",
            ("Q gates", "shift-register outputs", "detector wiring"),
            "Look for detector leads near the gate lines.",
        ),
    ),
    # ----------------------------------------------------------- ambient
    Rule(
        "ambient/*/leak",
        E(
            "The dark level rises toward the bottom of the travel: ambient light leaking past the "
            "shroud as the chamber overlap shrinks.",
            ("shroud", "lid"),
            "Repeat with the room dark; inspect the shroud seal.",
        ),
    ),
    Rule(
        "ambient/*/flicker",
        E(
            "120 Hz in the dark: room lighting reaches the detector.",
            ("lid", "shroud"),
            "Close the lid / switch the room lights off and repeat.",
        ),
    ),
    # ----------------------------------------------------------- mechanics
    Rule(
        "mech/backlash",
        E(
            "The up-pass curves sit below the down-pass ones by this much: slack in the drive on "
            "every reversal (lead-screw nut, couplers, gearbox).",
            ("M6 rods and nuts", "5-6 mm couplers", "28BYJ-48 gearboxes"),
            "Tighten the coupler grub screws; check nut play; repeat the reference heights.",
        ),
    ),
    Rule(
        "mech/step_loss",
        E(
            "The stage falls further behind as it climbs: a motor is losing steps going up (load, "
            "binding, or low drive).",
            ("M1", "M2", "ULN2003", "lead screws"),
            "Jog up slowly and watch both sides; check for binding; compare the two sides against "
            "a ruler at the top.",
        ),
    ),
    Rule(
        "mech/repeatability",
        E(
            "Repeated visits to one height do not land in the same place.",
            ("couplers", "lead screws"),
            "Repeat the reference heights; inspect the couplers.",
        ),
    ),
    Rule(
        "mech/lockstep",
        E(
            "The two sides ended a move at different positions.",
            ("M1", "M2"),
            "Level the top by hand; set the top again.",
        ),
    ),
    Rule(
        "mech/settle",
        E(
            "The dark reading took long to settle after a move.",
            ("mechanics", "room light"),
            "Check for vibration and for flicker.",
        ),
    ),
    Rule(
        "mech/travel",
        E(
            "The tracked travel differs from the configured one (or between the sides).",
            ("stage limits",),
            "Re-mark the top and bottom.",
        ),
    ),
    # ----------------------------------------------------------- trend
    Rule(
        "trend/compare",
        E(
            "The response changed against the previous baseline; where it sits points to the "
            "part (one hole: that LED or its alignment; one detector: that detector or its front "
            "end; everything: supply, geometry or the sample).",
            ("see the localisation",),
            "Repeat with the same sample; check what changed.",
        ),
    ),
    Rule(
        "trend/control",
        E(
            "A metric left its control limits against the baselines.",
            ("see the metric",),
            "Look at that metric's control chart.",
        ),
    ),
)


RULES = (
    *RULES,
    Rule("optics/effectiveness", E(
        "Response lower than the reference of the same sample.",
        ("LEDs", "window", "alignment"), "See trend/compare for where the change sits.")),
    Rule("elec/coupling_states", E(
        "A CE-only or wrong-rail state showed signal (firmware 2.5.0 debug states).",
        ("DRV1/DRV2", "CE wiring", "rail map"), "Run T05.1; check the rail map.")),
    Rule("elec/rails", E(
        "A supply rail sagged or the ground moved under LED load (A2/A3 monitoring).",
        ("rail supplies", "GND"), "Meter the rails with RAIL B lit.")),
    Rule("mech/home_sensors", E(
        "The home sensors disagree with the step count.", ("home sensors", "M1", "M2"),
        "Check the sensor alignment; re-home.")),
    Rule("ambient/lid", E(
        "The dark changes with the lid ajar: light reaches the detector past the lid.",
        ("lid", "shroud"), "Check the lid seal.")),
)  # fmt: skip


_PD = E(
    "A consequence of the InGaAs signal being electrical, not light (see "
    "optics/ingaas/electrical_only): the photodiode is not connected to the amplifier.",
    ("D1", "U5", "SUM", "TIA_REF"),
    "Fault tree 'InGaAs coupling': meter the D1 leads and the pin 2/3 wiring of U5.",
)
_PD_WHEN: When = lambda f, c: _status(c, "optics/ingaas/electrical_only", Status.FAIL)  # noqa: E731
# Checked first: in the disconnected-photodiode case these symptoms are not the window
# or the grounding.
RULES = (
    Rule("optics/ingaas/throughput", _PD, when=_PD_WHEN),
    Rule("elec/ingaas/ground_shift", _PD, when=_PD_WHEN),
    Rule("optics/ingaas/snr", _PD, when=_PD_WHEN),
    Rule("elec/ingaas/hum", E(
        "Mains hum is much larger with the photodiode disconnected: the TIA input is left "
        "open and picks it up.", ("D1", "U5 pin-2 node", "earth bond"),
        "Reconnect D1 first; then check the earth bond if the hum remains.")
        , when=_PD_WHEN),
    *RULES,
)  # fmt: skip


def _match(pattern: str, fid: str) -> bool:
    pat = pattern.replace("hNN", "h[0-9][0-9]")
    return fnmatch.fnmatchcase(fid, pat)


def explain(f: Finding, ctx: Ctx) -> Explanation | None:
    """The explanation of a flagged finding (None for PASS/SKIP or with no rule)."""
    if f.status not in (Status.WARN, Status.FAIL, Status.ERROR):
        return None
    for r in RULES:
        if _match(r.pattern, f.id) and (r.when is None or r.when(f, ctx)):
            e = r.explanation
            hole = _hole(f)
            if hole != "n":  # name the hole's own parts
                own = {"LED": f"LED{hole}", "Q (MOSFET)": f"Q{hole}"}
                parts = tuple(own.get(p, p) for p in e.parts)
                e = Explanation(e.cause, parts, e.check.replace("lio ch N", f"lio ch {hole}"))
            return e
    return None


def explain_all(findings: list[Finding]) -> dict[str, Explanation]:
    ctx = {f.id: f for f in findings}
    out = {}
    for f in findings:
        e = explain(f, ctx)
        if e is not None:
            out[f.id] = e
    return out
