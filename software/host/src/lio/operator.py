"""The person at the bench, for interactive (I) and motion (M) tests.

Checks never call ``input()`` directly; they ask an :class:`Operator`. Each
question has a ``key`` naming what is asked (for example ``motor_up:1``), so a
:class:`SimOperator` can answer from the simulator's physical truth: which
LEDs really lit, in what order, and whether a motor really turned.

Answering ``a`` (or ``abort``) at any console prompt raises :class:`Abort`; the
test runner then turns everything off and records the test as skipped.
"""

from __future__ import annotations

import abc
from collections.abc import Callable

from lio.sim import SimulatedLIO


class Abort(Exception):
    """The operator aborted the test."""


class Operator(abc.ABC):
    @abc.abstractmethod
    def inform(self, message: str) -> None:
        """Show a message; no answer needed."""

    @abc.abstractmethod
    def act(self, key: str, prompt: str) -> None:
        """Ask the operator to do something and confirm when done."""

    @abc.abstractmethod
    def confirm(self, key: str, prompt: str) -> bool:
        """A yes/no observation."""

    @abc.abstractmethod
    def number(self, key: str, prompt: str, unit: str) -> float | None:
        """A measured value; None if the operator skips it."""

    @abc.abstractmethod
    def text(self, key: str, prompt: str) -> str:
        """Free text (an optional remark)."""


ABORT_WORDS = ("a", "abort")


class ConsoleOperator(Operator):
    """Prompts on the terminal. ``ask``/``say`` are injectable for pytest and tests."""

    def __init__(
        self,
        ask: Callable[[str], str] = input,
        say: Callable[[str], None] = print,
    ) -> None:
        self._ask = ask
        self._say = say

    def _get(self, prompt: str) -> str:
        answer = self._ask(prompt).strip()
        if answer.lower() in ABORT_WORDS:
            raise Abort("aborted by the operator")
        return answer

    def inform(self, message: str) -> None:
        self._say(f"\n[LIO] {message}")

    def act(self, key: str, prompt: str) -> None:
        self._get(f"\n[LIO] {prompt}\n      Press Enter when done (a = abort): ")

    def confirm(self, key: str, prompt: str) -> bool:
        while True:
            a = self._get(f"\n[LIO] {prompt} [y/n, a = abort]: ").lower()
            if a in ("y", "yes"):
                return True
            if a in ("n", "no"):
                return False
            self._say("      please answer y or n")

    def number(self, key: str, prompt: str, unit: str) -> float | None:
        while True:
            a = self._get(f"\n[LIO] {prompt} [{unit}; blank = skip, a = abort]: ")
            if not a:
                return None
            try:
                return float(a)
            except ValueError:
                self._say("      please enter a number")

    def text(self, key: str, prompt: str) -> str:
        return self._get(f"\n[LIO] {prompt} [optional, a = abort]: ")


class SimOperator(Operator):
    """Answers from the simulator's ground truth, as a careful operator would.

    Keys understood (anything else is answered yes / skipped):

    - ``chamber_clear``: yes
    - ``walk_start`` then ``walk_visible`` / ``walk_camera``: compares the holes
      that physically lit since the walk started with the expected order
    - ``motor_up:<m>`` / ``motor_down:<m>``: did motor m physically move that way
      since the previous motor question
    - ``meter_ready:<rail>`` then ``meter_ma:<rail>``: the rail current if an
      emitter on that rail was lit for most of the flash, else 0
    - ``open_chamber`` / ``close_chamber``: open or close the simulated lid
    """

    def __init__(self, sim: SimulatedLIO, answers: dict[str, object] | None = None) -> None:
        self.sim = sim
        self.answers = dict(answers or {})
        self.log: list[tuple[str, str, object]] = []  # (key, prompt, answer)
        self._marks: dict[str, float] = {}
        self._motor_seen = [m.physical for m in sim.motors]
        self._walk_notes: dict[str, str] = {}

    def _record(self, key: str, prompt: str, answer: object) -> None:
        self.log.append((key, prompt, answer))

    def _lit_since(self, t0: float) -> list[tuple[float, float, int]]:
        log = list(self.sim.light_log)
        log += [(t, self.sim.clock, h) for h, t in self.sim._light_since.items()]
        return sorted(e for e in log if e[0] >= t0 - 1e-9)

    def inform(self, message: str) -> None:
        self._record("inform", message, None)

    def act(self, key: str, prompt: str) -> None:
        self._marks[key.split(":")[0]] = self.sim.clock
        if key == "open_chamber":
            self.sim.chamber_open = True
        elif key == "close_chamber":
            self.sim.chamber_open = False
        self._record(key, prompt, None)
        if self.answers.get(key) == "abort":
            raise Abort("aborted by the (simulated) operator")

    def confirm(self, key: str, prompt: str) -> bool:
        if key in self.answers:
            answer = bool(self.answers[key])
        elif key in ("walk_visible", "walk_camera"):
            from lio.suite.checks.interactive import walk_groups

            eye, camera, _ = walk_groups(self.sim.cfg)
            want = eye if key == "walk_visible" else camera
            seen = [h for _, _, h in self._lit_since(self._marks.get("walk_start", 0.0))]
            order = [h for i, h in enumerate(seen) if h in want and (i == 0 or seen[i - 1] != h)]
            answer = order == want
            # what a careful operator would name: missing holes and holes out of place
            wrong = {h for h in want if h not in order}
            present = [h for h in want if h in order]
            wrong |= {w for w, o in zip(present, order, strict=False) if w != o}
            self._walk_notes[f"{key}_note"] = " ".join(str(h) for h in sorted(wrong))
        elif key.startswith(("motor_up:", "motor_down:")):
            i = int(key.split(":")[1]) - 1
            moved = self.sim.motors[i].physical - self._motor_seen[i]
            self._motor_seen[i] = self.sim.motors[i].physical
            answer = moved > 0 if key.startswith("motor_up") else moved < 0
        else:
            answer = True
        self._record(key, prompt, answer)
        return answer

    def number(self, key: str, prompt: str, unit: str) -> float | None:
        if key in self.answers:
            v = self.answers[key]
            answer = None if v is None else float(v)  # type: ignore[arg-type]
        elif key.startswith("meter_ma:"):
            rail = key.split(":")[1]
            holes = set(self.sim.cfg.rail_holes(rail))
            t0 = self._marks.get("meter_ready", 0.0)
            on = sum(t1 - ta for ta, t1, h in self._lit_since(t0) if h in holes)
            flash = self.sim.clock - t0
            lit = flash > 0 and on >= 0.5 * flash
            current = float(self.sim.cfg.section.num(f"rails.{rail}.current_ma"))
            answer = current if lit else 0.0
        else:
            answer = None
        self._record(key, prompt, answer)
        return answer

    def text(self, key: str, prompt: str) -> str:
        answer = str(self.answers.get(key, self._walk_notes.get(key, "")))
        self._record(key, prompt, answer)
        return answer
