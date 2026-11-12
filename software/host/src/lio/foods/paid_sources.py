"""Paid product-data sources: interface stubs only, disabled (plan LIO-SW-COMP-002, WP8).

LIO does not license paid data. These stubs document how a licensed source would plug
into :class:`lio.foods.lookup.Lookup` if a licence is ever obtained. They make no
network calls, hold no keys, and are not in the lookup's source list.

- **GS1 US Data Hub** (and GDSN data pools such as 1WorldSync or Syndigo): brand-owner
  product data keyed by GTIN. Verified GTIN ownership ("Verified by GS1") is free to
  look up by hand, but bulk API access and attribute data need a subscription.
- **Label Insight (NielsenIQ)**: label transcriptions behind SmartLabel. The existing
  ``smartlabel`` source in :mod:`lio.foods.lookup` is this adapter's working form. It
  is off unless ``LookupSettings.smartlabel_key`` is set, and smartlabel.org pages are
  only linked to, never scraped.

Whatever a paid source returns is an UNVERIFIED database value, like FDC: a third
party's transcription, not the label. It may become corroboration or a candidate in a
composition record, never a fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .barcode import Gtin


class PaidSourceDisabled(RuntimeError):
    """Raised by every stub: no paid source is licensed or enabled."""


class ProductSource(Protocol):
    """The contract a lookup source meets (the same as ``Lookup.usda`` and the others).

    ``fetch`` returns ``(info, raw)``: ``info`` is the normalised dict of
    :func:`lio.foods.lookup.empty_info` (or None when the product is unknown), ``raw``
    is the source's answer, stored byte-for-byte as evidence. Network and HTTP
    failures raise ``OSError``/``urllib.error.URLError``; a malformed answer raises
    ``ValueError``.
    """

    @property
    def name(self) -> str: ...

    @property
    def enabled(self) -> bool: ...

    def fetch(self, gtin: Gtin) -> tuple[dict[str, Any] | None, Any]: ...


@dataclass(frozen=True)
class Gs1DataHubStub:
    """GS1 US Data Hub (Product), by GTIN. Disabled: needs a paid subscription."""

    name: str = "gs1_datahub"
    enabled: bool = False

    def fetch(self, gtin: Gtin) -> tuple[dict[str, Any] | None, Any]:
        raise PaidSourceDisabled(
            f"{self.name}: not licensed; GS1 Data Hub access needs a paid subscription"
        )


@dataclass(frozen=True)
class LabelInsightStub:
    """Label Insight bulk feed. Disabled; see the key-gated ``smartlabel`` source."""

    name: str = "label_insight"
    enabled: bool = False

    def fetch(self, gtin: Gtin) -> tuple[dict[str, Any] | None, Any]:
        raise PaidSourceDisabled(
            f"{self.name}: not licensed; Label Insight data needs a commercial agreement"
        )


STUBS: tuple[ProductSource, ...] = (Gs1DataHubStub(), LabelInsightStub())
