"""Paid-source adapters are documentation-only stubs, disabled and never in the lookup."""

import inspect

import pytest

from lio.foods import lookup, paid_sources
from lio.foods.barcode import normalise


@pytest.mark.parametrize("stub", paid_sources.STUBS)
def test_stub_disabled(stub: paid_sources.ProductSource) -> None:
    assert not stub.enabled
    with pytest.raises(paid_sources.PaidSourceDisabled):
        stub.fetch(normalise("341520314643"))


def test_stubs_not_in_lookup() -> None:
    src = inspect.getsource(lookup.Lookup.lookup)
    for stub in paid_sources.STUBS:
        assert stub.name not in src
    assert lookup.LookupSettings().smartlabel_key == ""
