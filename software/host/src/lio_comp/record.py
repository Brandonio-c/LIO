"""Assemble a record bundle (spec §3.3) from snapshots, rules and stated assumptions.

Every fact is created the same way the verifier checks it: the locator is read
from the snapshot bytes, the named rule turns that text into ``value_raw``, and
the interpretation turns ``value_raw`` into an interval. Nothing is typed in.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lio_comp import catalog
from lio_comp.evidence import canonical_json, get
from lio_verify import textrules
from lio_verify.interpret import interpret
from lio_verify.locate import read, resolve

EXTRACTOR_VERSION = "lio_comp.extract@1"
DERIVER_VERSION = "lio_comp.derive@1"
BOUNDER_VERSION = "lio_comp.bound@1"


class RecordError(RuntimeError):
    pass


class RecordBuilder:
    def __init__(
        self,
        store: Path,
        tables: dict[str, dict[str, Any]],
        *,
        record_id: str,
        gtin: str,
        product_name: str,
        variant_note: str,
    ) -> None:
        self.store = store
        self.tables = tables
        self.cat = catalog.load(store)
        self.head: dict[str, Any] = {
            "schema_version": "1",
            "record_id": record_id,
            "gtin": gtin,
            "product_name": product_name,
            "variant_note": variant_note,
            "physical_sample": {
                "sample_code": "",
                "lot": "",
                "photos": [],
                "attestation": None,
                "assumptions": [],
            },
            "variables": [],
        }
        self.sources: dict[str, dict[str, Any]] = {}
        self._bytes: dict[str, bytes] = {}
        self.assumptions: dict[str, dict[str, Any]] = {}
        self.facts: list[dict[str, Any]] = []
        self.substances: list[dict[str, Any]] = []
        self.ingredients: list[dict[str, Any]] = []
        self.derivations: list[dict[str, Any]] = []
        self.constraints: list[dict[str, Any]] = []
        self.bounds: list[dict[str, Any]] = []
        self.attestations: list[dict[str, Any]] = []
        self.estimates: list[dict[str, Any]] = []
        self.notes: list[str] = []

    # ---------------------------------------------------------------- sources
    def source(self, source_id: str, doc: str, identifiers: dict[str, str] | None = None) -> bytes:
        sha = self.cat[doc]
        data = get(self.store, sha)
        media = json.loads((self.store / "manifest" / f"{sha}.json").read_text())["media_type"]
        self.sources[source_id] = {
            "source_id": source_id,
            "sha256": sha,
            "media_type": media,
            "identifiers": {"catalog_name": doc, **(identifiers or {})},
        }
        self._bytes[source_id] = data
        return data

    def data(self, source_id: str) -> bytes:
        return self._bytes[source_id]

    def located(self, source_id: str, locator: dict[str, Any]) -> dict[str, Any]:
        """The locator with its ``text`` filled in from the snapshot (and checked)."""
        loc = dict(locator)
        loc["text"] = read(loc, self.data(source_id))
        resolve(loc, self.data(source_id))
        return loc

    # ------------------------------------------------------------ assumptions
    def assume(self, aid: str, kind: str, text: str, rule_ref: str | None = None) -> str:
        a: dict[str, Any] = {"id": aid, "kind": kind, "text": text}
        if rule_ref:
            a["rule_ref"] = rule_ref
        if aid in self.assumptions and self.assumptions[aid] != a:
            raise RecordError(f"assumption {aid} stated twice differently")
        self.assumptions[aid] = a
        ps = self.head["physical_sample"]["assumptions"]
        if kind == "sample_identity" and aid not in ps:
            ps.append(aid)  # identity of the physical sample: applies to the whole record
        return aid

    # ------------------------------------------------------------------ facts
    def fact(
        self,
        fid: str,
        quantity: str,
        basis: str,
        source_id: str,
        locator: dict[str, Any],
        rule: str,
        interpretation: dict[str, Any],
        *,
        substance: dict[str, Any] | None = None,
        assumptions: tuple[str, ...] = (),
        evidence_class: str = "document",
    ) -> dict[str, Any]:
        loc = self.located(source_id, locator)
        value_raw = textrules.apply(rule, loc["text"])
        iv, unit = interpret(value_raw, interpretation, self.tables)
        for a in assumptions:
            if a not in self.assumptions:
                raise RecordError(f"{fid}: assumption {a} not stated")
        f: dict[str, Any] = {
            "id": fid,
            "quantity": quantity,
            "value_raw": value_raw,
            "basis": basis,
            "source_id": source_id,
            "locator": loc,
            "rule": rule,
            "interpretation": interpretation,
            "value": iv.to_json(unit),
            "evidence_class": evidence_class,
            "assumptions": list(assumptions),
        }
        if substance:
            f["substance"] = substance
        self.facts.append(f)
        return f

    # ------------------------------------------------- substances, ingredients
    def substance(
        self,
        sid: str,
        unii: str,
        source_id: str,
        unii_locator: dict[str, Any],
        *,
        name_locator: dict[str, Any] | None = None,
        formula_locator: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        s: dict[str, Any] = {
            "id": sid,
            "unii": unii,
            "source_id": source_id,
            "unii_locator": self.located(source_id, unii_locator),
        }
        if s["unii_locator"]["text"] != unii:
            raise RecordError(f"{sid}: source says UNII {s['unii_locator']['text']}, not {unii}")
        if name_locator:
            s["name_locator"] = self.located(source_id, name_locator)
        if formula_locator:
            s["formula_locator"] = self.located(source_id, formula_locator)
            s["formula"] = s["formula_locator"]["text"]
        self.substances.append(s)
        return s

    def ingredient(
        self,
        iid: str,
        list_id: str,
        position: int,
        role: str,
        source_id: str,
        name_locator: dict[str, Any],
        *,
        unii_locator: dict[str, Any] | None = None,
        substance: str | None = None,
        list_rule: str | None = None,
    ) -> dict[str, Any]:
        """An ingredient's identity. With ``list_rule`` (``list_item@1:<n>``) the locator
        points at the whole list and the rule picks the item."""
        ing: dict[str, Any] = {
            "id": iid,
            "list_id": list_id,
            "position": position,
            "role": role,
            "source_id": source_id,
            "name_locator": self.located(source_id, name_locator),
        }
        text = ing["name_locator"]["text"]
        if list_rule:
            ing["list_rule"] = list_rule
            text = textrules.apply(list_rule, text)
        ing["name_verbatim"] = text
        if unii_locator:
            ing["unii_locator"] = self.located(source_id, unii_locator)
            ing["unii"] = ing["unii_locator"]["text"]
        if substance:
            ing["substance"] = substance
        self.ingredients.append(ing)
        return ing

    def note(self, text: str) -> None:
        self.notes.append(text)

    # ----------------------------------------------------------------- output
    def bundle(self) -> dict[str, Any]:
        used = sorted(self.tables)
        return {
            **self.head,
            "sources": [self.sources[k] for k in sorted(self.sources)],
            "assumptions": [self.assumptions[k] for k in sorted(self.assumptions)],
            "substances": self.substances,
            "ingredients": self.ingredients,
            "facts": self.facts,
            "derivations": self.derivations,
            "constraints": self.constraints,
            "bounds": self.bounds,
            "attestations": self.attestations,
            "unverified_layer": {"estimates": self.estimates, "notes": self.notes},
            "toolchain": {
                "extractor_version": EXTRACTOR_VERSION,
                "deriver_version": DERIVER_VERSION,
                "bounder_version": BOUNDER_VERSION,
                "rules_versions": {t: self.tables[t]["version"] for t in used},
            },
        }

    def write(self, out_dir: Path) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        p = out_dir / f"{self.head['record_id']}.json"
        p.write_bytes(canonical_json(self.bundle()))
        return p
