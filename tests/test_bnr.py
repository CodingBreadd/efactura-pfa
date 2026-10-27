import os
from datetime import date
from decimal import Decimal

import pytest

from efactura import bnr

# The 2025 files use http://www.bnr.ro/xsd, the 2026 ones https://www.bnr.ro/xsd.
XML = b"""<?xml version="1.0" encoding="utf-8"?>
<DataSet xmlns="%s"><Body>
<Cube date="2026-10-22"><Rate currency="EUR">5.3400</Rate><Rate currency="HUF" multiplier="100">1.4500</Rate></Cube>
<Cube date="2026-10-23"><Rate currency="EUR">5.3495</Rate></Cube>
<Cube date="2026-10-26"><Rate currency="EUR">5.3467</Rate></Cube>
</Body></DataSet>"""


@pytest.mark.parametrize("ns", [b"http://www.bnr.ro/xsd", b"https://www.bnr.ro/xsd"])
def test_parse(ns):
    rates = bnr.parse(XML % ns, "HUF")
    assert rates == {date(2026, 10, 22): Decimal("0.0145")}


def test_rate_is_from_before_the_invoice_date(monkeypatch):
    monkeypatch.setattr(bnr, "_fetch", lambda url, timeout: XML % b"https://www.bnr.ro/xsd")
    assert bnr.rate_for("EUR", date(2026, 10, 26)) == (date(2026, 10, 23), Decimal("5.3495"))  # Monday
    assert bnr.rate_for("EUR", date(2026, 10, 27)) == (date(2026, 10, 26), Decimal("5.3467"))
    with pytest.raises(LookupError):
        bnr.rate_for("USD", date(2026, 10, 27))


@pytest.mark.skipif(os.environ.get("EFACTURA_OFFLINE") == "1", reason="offline")
def test_live_rate():
    published, rate = bnr.rate_for("EUR", date(2026, 3, 2))
    assert published == date(2026, 2, 27) and Decimal("4") < rate < Decimal("7")
