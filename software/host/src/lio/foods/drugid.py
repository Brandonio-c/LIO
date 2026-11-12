"""Barcode -> NDC -> SPL resolution for OTC drugs (plan WP1).

A UPC that starts with 3 carries a 10-digit NDC, but it can be retired or stale
(Citrucel: 0068-0418-30, labeled today as Haleon 0135-0089; Care One ibuprofen:
41520-314-64, labeled 41520-745-xx). So:

1. **RxNav status** of each NDC the UPC can carry (``ndcstatus``, history): ACTIVE,
   OBSOLETE, ALIEN or UNKNOWN. RxNav says which *drug concept* an NDC belongs to;
   it is never used as proof that a barcode is a particular product.
2. **DailyMed by NDC**: is that NDC in a current SPL? If yes, the SPL is a lead.
3. If no embedded NDC is in an SPL, the app asks for a **photo of the NDC printed
   on the carton**. The operator confirms the span; the printed NDC goes to
   DailyMed (``spls.json?ndc=``, ``ndcs.json``, ``history.json``).
4. The confirmed link is appended to the **crosswalk**
   (``software/host/data/crosswalk/gtin_links.jsonl``), so a re-scan resolves at
   once. A link whose SPL has a newer version is flagged for re-confirmation.

Every RxNav and DailyMed answer goes through :class:`lio.foods.lookup.Lookup`,
so it is snapshotted by SHA-256 when an evidence store is configured.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .barcode import Gtin, ndc11, ndc_candidates
from .lookup import Lookup

RXNAV = "https://rxnav.nlm.nih.gov/REST"
CROSSWALK = Path(__file__).resolve().parents[3] / "data" / "crosswalk" / "gtin_links.jsonl"
METHODS = ("printed_ndc", "name_search_confirmed")


class Throttle:
    """At most ``rate`` calls per second (RxNav asks for about 20)."""

    def __init__(self, rate: float) -> None:
        self.gap = 1.0 / rate
        self.last = 0.0
        self.lock = threading.Lock()

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            if now - self.last < self.gap:
                time.sleep(self.gap - (now - self.last))
            self.last = time.monotonic()


_rxnav_throttle = Throttle(15.0)


def dashed_from_11(n11: str, pattern: str) -> str:
    """11-digit NDC -> dashed 10-digit in a given pattern (for DailyMed queries)."""
    lab, prod, pkg = n11[:5], n11[5:9], n11[9:]
    if pattern == "4-4-2":
        return f"{lab[1:]}-{prod}-{pkg}"
    if pattern == "5-3-2":
        return f"{lab}-{prod[1:]}-{pkg}"
    return f"{lab}-{prod}-{pkg[1:]}"


class DrugResolver:
    def __init__(self, lookup: Lookup, crosswalk: Path | None = None) -> None:
        self.lk = lookup
        self.crosswalk = crosswalk or CROSSWALK  # read at call time (tests point it elsewhere)

    # ------------------------------------------------------------------- RxNav
    def _rx(self, path: str) -> Any:
        _rxnav_throttle.wait()
        return self.lk._get(f"{RXNAV}/{path}")

    def ndc_status(self, n11: str) -> dict[str, Any]:
        d = self._rx(f"ndcstatus.json?ndc={n11}&history=1")
        s = (d or {}).get("ndcStatus") or {}
        return {
            "ndc11": n11,
            "status": str(s.get("status") or "UNKNOWN"),
            "rxcui": str(s.get("rxcui") or ""),
            "concept": str(s.get("conceptName") or ""),
            "sources": list(((s.get("sourceList") or {}).get("sourceName")) or []),
            "history": list(s.get("ndcHistory") or []),
            "note": "RxNav: drug-concept equivalence only, never product identity",
        }

    # ---------------------------------------------------------------- DailyMed
    def spls_for_ndc(self, ndc: str) -> list[dict[str, Any]]:
        try:
            d = self.lk._get(f"{self.lk.s.dailymed_url}/spls.json?ndc={urllib.parse.quote(ndc)}")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []
            raise
        return [
            {"setid": str(x.get("setid") or ""), "version": int(x.get("spl_version") or 0),
             "title": str(x.get("title") or "")}
            for x in (d.get("data") if isinstance(d, dict) else None) or []
        ]  # fmt: skip

    def spl_ndcs(self, setid: str) -> tuple[int, list[str]]:
        d = self.lk._get(f"{self.lk.s.dailymed_url}/spls/{setid}/ndcs.json")
        data = (d or {}).get("data") or {}
        return int(data.get("spl_version") or 0), [
            str(x.get("ndc")) for x in data.get("ndcs") or []
        ]

    def spl_version(self, setid: str) -> int:
        d = self.lk._get(f"{self.lk.s.dailymed_url}/spls/{setid}/history.json")
        hist = ((d or {}).get("data") or {}).get("history") or []
        return max((int(h.get("spl_version") or 0) for h in hist), default=0)

    def resolve_printed(self, ndc: str) -> dict[str, Any] | None:
        """A confirmed printed NDC -> the SPL that lists it as a package NDC (exactly one)."""
        spls = self.spls_for_ndc(ndc)
        hits = []
        for s in spls:
            version, ndcs = self.spl_ndcs(s["setid"])
            if ndc in ndcs:
                hits.append({**s, "version": version, "ndcs": ndcs})
        if len(hits) != 1:
            return None
        h = hits[0]
        h["latest_version"] = self.spl_version(h["setid"])
        return h

    # --------------------------------------------------------------- crosswalk
    def links(self) -> list[dict[str, Any]]:
        if not self.crosswalk.exists():
            return []
        return [json.loads(ln) for ln in self.crosswalk.read_text().splitlines() if ln.strip()]

    def link_for(self, gtin14: str) -> dict[str, Any] | None:
        mine = [x for x in self.links() if x.get("gtin") == gtin14]
        return mine[-1] if mine else None  # the latest confirmation wins

    def add_link(self, row: dict[str, Any]) -> dict[str, Any]:
        """Append an attested link (never rewrites earlier lines)."""
        need = {"gtin", "ndc11", "setid", "spl_version", "evidence", "attestation", "method"}
        if not need <= set(row) or row["method"] not in METHODS:
            raise ValueError(f"crosswalk row needs {sorted(need)} and a method in {METHODS}")
        if not str(row["attestation"].get("operator") or "").strip():
            raise ValueError("a crosswalk link needs the operator who confirmed it")
        self.crosswalk.parent.mkdir(parents=True, exist_ok=True)
        with self.crosswalk.open("a") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
        return row

    # ---------------------------------------------------------------- resolve
    def resolve(self, gtin: Gtin) -> dict[str, Any]:
        """Everything known about a drug barcode, and whether a printed NDC is needed."""
        out: dict[str, Any] = {"gtin": gtin.gtin14, "embedded": [], "crosswalk": None,
                               "needs_printed_ndc": False, "spl": None}  # fmt: skip
        link = self.link_for(gtin.gtin14)
        if link is not None:
            try:
                latest = self.spl_version(link["setid"])
            except (urllib.error.URLError, OSError, ValueError):
                latest = 0
            out["crosswalk"] = {**link, "stale": bool(latest and latest != link["spl_version"]),
                                "latest_version": latest}  # fmt: skip
            out["spl"] = {
                "setid": link["setid"],
                "version": link["spl_version"],
                "via": "crosswalk",
            }
            return out
        for c in ndc_candidates(gtin):
            st = self.ndc_status(ndc11(c.ndc))
            spls = self.spls_for_ndc(c.ndc)
            out["embedded"].append({"pattern": c.pattern, "ndc": c.ndc, **st, "spls": spls})
            if spls and out["spl"] is None:
                out["spl"] = {
                    **spls[0],
                    "via": f"embedded NDC {c.ndc} (a lead: confirm the product)",
                }
        # Embedded NDC is in no SPL (retired, stale or compendia-only): ask for the printed one.
        out["needs_printed_ndc"] = bool(out["embedded"]) and out["spl"] is None
        return out


@dataclass(frozen=True)
class NdcCandidate:
    text: str  # the span as read ("NDC 41520-745-18")
    ndc: str
    ndc11: str
    box: dict[str, int]
