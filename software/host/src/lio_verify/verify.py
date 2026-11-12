"""The independent verifier (spec §6). Imports nothing from ``lio`` or ``lio_comp``.

Checks, in order: schema and no JSON floats; sources (hash, manifest); facts
(locator, rule, interpretation); substances and ingredients; derivations;
constraints; bounds (witnesses, z3); attestations; assumptions. Each field gets
a status:

- VERIFIED: every check passed, from documents only;
- ATTESTED: every check passed, but it rests on a human attestation (photo);
- UNVERIFIED: its own checks passed or were not possible, but an input failed;
- FAILED: one of its own checks failed.

The record passes only if nothing is FAILED (fail closed). No network unless
``refetch`` is set, and then only to report whether upstream bytes changed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lio_verify import __version__, textrules
from lio_verify.expr import Context, ExprError, evaluate
from lio_verify.interpret import InterpretError, interpret, load_tables, split_ref, table
from lio_verify.interval import Interval, IntervalError
from lio_verify.locate import LocatorError, resolve
from lio_verify.lp import LpError, atoms, check_bound, data_check, has_unknowns, z3_problem

VERIFIED, ATTESTED, UNVERIFIED, FAILED = "VERIFIED", "ATTESTED", "UNVERIFIED", "FAILED"
INT_KEYS = {"start", "end", "x", "y", "w", "h", "position"}


@dataclass
class Field:
    kind: str
    id: str
    status: str
    problems: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    value: dict[str, Any] | None = None

    def to_json(self) -> dict[str, Any]:
        d: dict[str, Any] = {"kind": self.kind, "id": self.id, "status": self.status}
        if self.problems:
            d["problems"] = self.problems
        if self.assumptions:
            d["assumptions"] = self.assumptions
        if self.value is not None:
            d["value"] = self.value
        return d


@dataclass
class Report:
    record: str
    fields: list[Field] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    assumptions: list[dict[str, Any]] = field(default_factory=list)
    rules_versions: dict[str, int] = field(default_factory=dict)
    sources: list[dict[str, Any]] = field(default_factory=list)
    refetch: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors and all(f.status != FAILED for f in self.fields)

    def counts(self) -> dict[str, int]:
        out = {VERIFIED: 0, ATTESTED: 0, UNVERIFIED: 0, FAILED: 0}
        for f in self.fields:
            out[f.status] += 1
        return out

    def to_json(self) -> dict[str, Any]:
        return {
            "verifier": f"lio_verify@{__version__}",
            "record": self.record,
            "result": "PASS" if self.ok else "FAIL",
            "counts": self.counts(),
            "errors": self.errors,
            "fields": [f.to_json() for f in self.fields],
            "assumptions": self.assumptions,
            "rules_versions": self.rules_versions,
            "sources": self.sources,
            "refetch": self.refetch,
        }


class _Float(Exception):
    pass


def _no_floats(obj: Any, path: str = "$") -> list[str]:
    """JSON numbers are allowed only as integer offsets/positions and rule versions."""
    out: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}"
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                if isinstance(v, float) or (k not in INT_KEYS and ".rules_versions" not in path):
                    out.append(f"JSON number at {p} (values must be rational strings)")
            else:
                out.extend(_no_floats(v, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out.append(f"JSON number at {path}[{i}]")
            else:
                out.extend(_no_floats(v, f"{path}[{i}]"))
    return out


def _load_record(path: Path) -> Any:
    def bad_float(s: str) -> Any:
        raise _Float(s)

    return json.loads(path.read_text(encoding="utf-8"), parse_float=bad_float)


class Verifier:
    def __init__(self, sources: Path, rules: Path, schema: Path | None = None) -> None:
        self.sources = sources
        self.rules = rules
        self.schema_path = schema or rules.parent / "schema" / "record.schema.json"
        self.tables = load_tables(rules)

    # ----------------------------------------------------------------- driver
    def verify(self, record_path: Path, *, refetch: bool = False) -> Report:
        rep = Report(record=str(record_path))
        try:
            rec = _load_record(record_path)
        except _Float as e:
            rep.errors.append(f"a JSON float in the record ({e}); values must be rational strings")
            return rep
        except (OSError, json.JSONDecodeError) as e:
            rep.errors.append(f"cannot read the record: {e}")
            return rep
        if not self._schema(rec, rep):
            return rep
        rep.errors.extend(_no_floats(rec))
        rep.rules_versions = dict(rec["toolchain"]["rules_versions"])
        rep.assumptions = rec["assumptions"]
        for tid, ver in rep.rules_versions.items():
            if tid not in self.tables:
                rep.errors.append(f"rule table {tid} is not in {self.rules}")
            elif self.tables[tid]["version"] != ver:
                rep.errors.append(
                    f"record pins {tid}@{ver}; rules directory has @{self.tables[tid]['version']}"
                )
        data = self._sources(rec, rep, refetch)
        status: dict[str, str] = {}
        self._attestations(rec, rep)
        self._assumptions(rec, rep)
        attested = {a["id"] for a in rec["attestations"]}
        self._facts(rec, rep, data, status, attested)
        self._identities(rec, rep, data, status)
        ctx = self._derivations(rec, rep, status)
        self._constraints(rec, rep, ctx, status)
        self._bounds(rec, rep, ctx, status)
        return rep

    # ----------------------------------------------------------------- checks
    def _schema(self, rec: Any, rep: Report) -> bool:
        try:
            import jsonschema

            schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
            errs = sorted(
                jsonschema.Draft202012Validator(schema).iter_errors(rec), key=lambda e: e.path
            )
        except (OSError, json.JSONDecodeError) as e:
            rep.errors.append(f"cannot load the schema: {e}")
            return False
        for err in errs[:20]:
            rep.errors.append(f"schema: {err.json_path}: {err.message[:200]}")
        return not errs

    def _sources(self, rec: dict[str, Any], rep: Report, refetch: bool) -> dict[str, bytes]:
        data: dict[str, bytes] = {}
        for s in rec["sources"]:
            sid, sha = s["source_id"], s["sha256"]
            blob = self.sources / "sha256" / sha[:2] / sha
            man_p = self.sources / "manifest" / f"{sha}.json"
            entry = {"source_id": sid, "sha256": sha, "status": "ok"}
            try:
                b = blob.read_bytes()
                if hashlib.sha256(b).hexdigest() != sha:
                    raise ValueError("bytes do not match their SHA-256")
                man = json.loads(man_p.read_text(encoding="utf-8"))
                if man.get("sha256") != sha or man.get("byte_length") != len(b):
                    raise ValueError("manifest does not match the bytes")
                if man.get("media_type") != s["media_type"]:
                    raise ValueError("manifest media type differs from the record")
                if not man.get("retrievals"):
                    raise ValueError("manifest has no retrieval")
                data[sid] = b
                entry["retrieved_at"] = man["retrievals"][-1]["retrieved_at"]
                entry["retrieval_url"] = man["retrievals"][-1]["retrieval_url"]
                if refetch:
                    rep.refetch.append(_refetch(sid, sha, entry["retrieval_url"]))
            except (OSError, ValueError, KeyError) as e:
                entry["status"] = f"FAILED: {e}"
                rep.errors.append(f"source {sid}: {e}")
            rep.sources.append(entry)
        return data

    def _attestations(self, rec: dict[str, Any], rep: Report) -> None:
        for a in rec["attestations"]:
            f = Field("attestation", a["id"], ATTESTED)
            if not a["signer"].strip() or not a["statement"].strip():
                f.status, f.problems = FAILED, ["missing signer or statement"]
            if "signature" not in a:
                f.problems.append("unsigned (no signing key configured)")
            rep.fields.append(f)
        ps = rec["physical_sample"].get("attestation")
        if ps and ps not in {a["id"] for a in rec["attestations"]}:
            rep.errors.append(f"physical_sample cites missing attestation {ps}")

    def _assumptions(self, rec: dict[str, Any], rep: Report) -> None:
        defined = [a["id"] for a in rec["assumptions"]]
        if len(set(defined)) != len(defined):
            rep.errors.append("an assumption id is defined twice")
        used: set[str] = set(rec["physical_sample"].get("assumptions", []))
        for group in ("facts", "derivations", "constraints", "bounds"):
            for x in rec[group]:
                used.update(x.get("assumptions", []))
        for f in rec["facts"]:
            if f["interpretation"]["kind"] == "as_stated":
                used.add(f["interpretation"]["assumption"])
        missing = sorted(used - set(defined))
        unused = sorted(set(defined) - used)
        if missing:
            rep.errors.append(f"assumptions cited but not stated: {missing}")
        if unused:
            rep.errors.append(f"assumptions stated but never cited: {unused}")

    def _facts(
        self,
        rec: dict[str, Any],
        rep: Report,
        data: dict[str, bytes],
        status: dict[str, str],
        attested: set[str],
    ) -> None:
        ings = {i["id"] for i in rec["ingredients"]}
        for f in rec["facts"]:
            fld = Field("fact", f["id"], VERIFIED, assumptions=list(f["assumptions"]))
            fld.value = f["value"]
            try:
                if f["source_id"] not in data:
                    raise ValueError(f"source {f['source_id']} failed or is missing")
                loc = f["locator"]
                text = resolve(loc, data[f["source_id"]])
                if loc["type"] == "image_bbox":
                    if f["evidence_class"] != "attested" or loc["attestation_id"] not in attested:
                        raise ValueError("an image_bbox fact needs an attestation")
                    fld.status = ATTESTED
                elif f["evidence_class"] != "document":
                    raise ValueError("a document locator with evidence_class attested")
                raw = textrules.apply(f["rule"], text)
                if raw != f["value_raw"]:
                    raise ValueError(f"rule {f['rule']} reads {raw!r}, not {f['value_raw']!r}")
                interp = f["interpretation"]
                if interp["kind"] == "rounded":
                    tid, ver, _ = split_ref(interp["rule"])
                    if rep.rules_versions.get(tid) != ver:
                        raise ValueError(f"{interp['rule']} is not the pinned version")
                if interp["kind"] == "as_stated" and interp["assumption"] not in f["assumptions"]:
                    raise ValueError("an as-stated value must cite its assumption")
                iv, unit = interpret(f["value_raw"], interp, self.tables)
                if iv.to_json(unit) != f["value"]:
                    raise ValueError(f"interpretation gives {iv} {unit}, not the stated value")
                sub = f.get("substance")
                if sub and sub["ingredient"] not in ings:
                    raise ValueError(f"substance cites unknown ingredient {sub['ingredient']}")
            except (LocatorError, textrules.RuleError, InterpretError, IntervalError) as e:
                fld.status, fld.problems = FAILED, [str(e)]
            except (ValueError, KeyError) as e:
                fld.status, fld.problems = FAILED, [str(e)]
            status[f["id"]] = fld.status
            rep.fields.append(fld)

    def _identities(
        self, rec: dict[str, Any], rep: Report, data: dict[str, bytes], status: dict[str, str]
    ) -> None:
        for s in rec["substances"]:
            fld = Field("substance", s["id"], VERIFIED)
            try:
                b = data[s["source_id"]]
                if resolve(s["unii_locator"], b) != s["unii"]:
                    raise ValueError("UNII does not match its source")
                if "name_locator" in s:
                    resolve(s["name_locator"], b)
                if "formula" in s and resolve(s["formula_locator"], b) != s["formula"]:
                    raise ValueError("formula does not match its source")
            except (LocatorError, KeyError, ValueError) as e:
                fld.status, fld.problems = FAILED, [str(e)]
            status[s["id"]] = fld.status
            rep.fields.append(fld)
        subs = {s["id"] for s in rec["substances"]}
        for i in rec["ingredients"]:
            fld = Field("ingredient", i["id"], VERIFIED)
            try:
                b = data[i["source_id"]]
                text = resolve(i["name_locator"], b)
                if "list_rule" in i:
                    text = textrules.apply(i["list_rule"], text)
                if text != i["name_verbatim"]:
                    raise ValueError("name does not match its source")
                if "unii" in i and resolve(i["unii_locator"], b) != i["unii"]:
                    raise ValueError("UNII does not match its source")
                if "substance" in i and i["substance"] not in subs:
                    raise ValueError(f"unknown substance {i['substance']}")
            except (LocatorError, textrules.RuleError, KeyError, ValueError) as e:
                fld.status, fld.problems = FAILED, [str(e)]
            status[i["id"]] = fld.status
            rep.fields.append(fld)

    def _context(self, rec: dict[str, Any], status: dict[str, str]) -> Context:
        formulas = {
            s["id"]: s["formula"]
            for s in rec["substances"]
            if "formula" in s and status.get(s["id"]) == VERIFIED
        }
        return Context({}, self.tables, dict(rec["toolchain"]["rules_versions"]), formulas)

    def _derivations(self, rec: dict[str, Any], rep: Report, status: dict[str, str]) -> Context:
        ctx = self._context(rec, status)
        for f in rec["facts"]:
            if status[f["id"]] != FAILED:
                ctx.values[f["id"]] = Interval.from_json(f["value"])
        for d in rec["derivations"]:
            fld = Field("derivation", d["id"], VERIFIED, assumptions=list(d["assumptions"]))
            fld.value = d["value"]
            deps = _refs(d["expr"])
            try:
                iv, unit = evaluate(d["expr"], ctx)
                if iv.to_json(unit) != d["value"]:
                    raise ValueError(f"re-evaluates to {iv} {unit}, not the stated value")
                fld.status = _inherit(deps, status)
                ctx.values[d["id"]] = (iv, unit)
            except ExprError as e:
                failed_inputs = [x for x in deps if status.get(x) == FAILED]
                fld.status = UNVERIFIED if failed_inputs else FAILED
                fld.problems = [f"inputs failed: {failed_inputs}"] if failed_inputs else [str(e)]
            except ValueError as e:
                fld.status, fld.problems = FAILED, [str(e)]
            status[d["id"]] = fld.status
            rep.fields.append(fld)
        return ctx

    def _constraints(
        self, rec: dict[str, Any], rep: Report, ctx: Context, status: dict[str, str]
    ) -> None:
        units = {v["name"]: v["unit"] for v in rec["variables"]}
        lists = table(self.tables, "list_ordering", rep.rules_versions.get("list_ordering", -1))
        ing_role = {i["id"]: i["role"] for i in rec["ingredients"]}
        var_ing = {v["name"]: v.get("ingredient") for v in rec["variables"]}
        all_atoms = []
        for c in rec["constraints"]:
            fld = Field("constraint", c["id"], VERIFIED, assumptions=list(c["assumptions"]))
            deps = _refs(c.get("lhs")) + _refs(c.get("rhs"))
            try:
                if c["kind"] == "ordered_desc":
                    tid, ver, key = split_ref(c.get("list_rule", "missing@0"))
                    pinned = rep.rules_versions.get("list_ordering")
                    ok_ref = tid == "list_ordering" and ver == pinned
                    spec = lists["lists"].get(key) if ok_ref else None
                    if spec is None or spec["order"] != "descending_weight":
                        raise ValueError(f"{c.get('list_rule')} is not a weight-ordered list")
                    for item in c["items"]:
                        ing = var_ing.get(item[2:])
                        if ing is None or ing_role.get(ing) in ("active", "inactive"):
                            raise ValueError(
                                f"{item} is not a food ingredient of a weight-ordered list"
                            )
                if has_unknowns(c):
                    all_atoms.extend(atoms(c, units, ctx))
                    fld.status = _inherit(deps, status)
                else:
                    got = data_check(c, ctx)
                    if got != c.get("status"):
                        raise ValueError(f"status is {got}, record says {c.get('status')}")
                    if got == "violated":
                        raise ValueError("data conflict: the constraint cannot hold")
                    fld.status = _inherit(deps, status)
            except (LpError, ExprError) as e:
                failed_inputs = [x for x in deps if status.get(x) == FAILED]
                fld.status = UNVERIFIED if failed_inputs else FAILED
                fld.problems = [f"inputs failed: {failed_inputs}"] if failed_inputs else [str(e)]
            except (ValueError, KeyError) as e:
                fld.status, fld.problems = FAILED, [str(e)]
            status[c["id"]] = fld.status
            rep.fields.append(fld)
        if all_atoms:
            import z3

            zctx = z3.Context()
            zc, _ = z3_problem(all_atoms, sorted(units), zctx)
            s = z3.Solver(ctx=zctx)
            s.add(*zc)
            if s.check() != z3.sat:
                rep.errors.append("the constraints on unknowns contradict each other")

    def _bounds(
        self, rec: dict[str, Any], rep: Report, ctx: Context, status: dict[str, str]
    ) -> None:
        units = {v["name"]: v["unit"] for v in rec["variables"]}
        for b in rec["bounds"]:
            fld = Field("bound", b["id"], VERIFIED, assumptions=list(b["assumptions"]))
            fld.value = b["result"]
            cited = {a for c in rec["constraints"] if c["id"] in b["constraints"]
                     for a in c["assumptions"]}  # fmt: skip
            missing = sorted(cited - set(b["assumptions"]))
            problems = check_bound(b, rec["constraints"], units, ctx)
            if missing:
                problems.append(f"does not carry its constraints' assumptions {missing}")
            if problems:
                fld.status, fld.problems = FAILED, problems
            else:
                fld.status = _inherit(b["constraints"], status)
            status[b["id"]] = fld.status
            rep.fields.append(fld)


def effective_assumptions(rec: dict[str, Any]) -> dict[str, list[str]]:
    """Every assumption a value rests on: its own, its inputs' (recursively), and the
    physical sample's identity assumptions."""
    base = set(rec["physical_sample"].get("assumptions", []))
    eff: dict[str, set[str]] = {}
    for f in rec["facts"]:
        own = set(f["assumptions"])
        if f["interpretation"]["kind"] == "as_stated":
            own.add(f["interpretation"]["assumption"])
        eff[f["id"]] = base | own
    for d in rec["derivations"]:
        eff[d["id"]] = base | set(d["assumptions"])
        for r in _refs(d["expr"]):
            eff[d["id"]] |= eff.get(r, set())
    for c in rec["constraints"]:
        eff[c["id"]] = base | set(c["assumptions"])
        for r in _refs(c.get("lhs")) + _refs(c.get("rhs")):
            eff[c["id"]] |= eff.get(r, set())
    for bd in rec["bounds"]:
        eff[bd["id"]] = base | set(bd["assumptions"])
        for cid in bd["constraints"]:
            eff[bd["id"]] |= eff.get(cid, set())
    return {k: sorted(v) for k, v in eff.items()}


def _refs(expr: Any) -> list[str]:
    if isinstance(expr, str):
        return [] if expr[:2] in ("C:", "N:", "U:", "V:", "M:") else [expr]
    if isinstance(expr, list):
        return [r for e in expr[1:] for r in _refs(e)]
    return []


def _inherit(deps: list[str], status: dict[str, str]) -> str:
    st = [status.get(d, FAILED) for d in deps]
    if any(s in (FAILED, UNVERIFIED) for s in st):
        return UNVERIFIED
    if any(s == ATTESTED for s in st):
        return ATTESTED
    return VERIFIED


def _refetch(sid: str, sha: str, url: str) -> dict[str, Any]:
    import urllib.request

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "lio-verify (refetch)"})
        with urllib.request.urlopen(req, timeout=60) as r:  # explicit --refetch only
            now = hashlib.sha256(r.read()).hexdigest()
        return {"source_id": sid, "upstream_changed": now != sha, "upstream_sha256": now}
    except OSError as e:
        return {"source_id": sid, "error": str(e)}


__all__ = [
    "ATTESTED",
    "FAILED",
    "UNVERIFIED",
    "VERIFIED",
    "Report",
    "Verifier",
    "effective_assumptions",
]
