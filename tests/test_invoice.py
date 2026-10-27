import os
from decimal import Decimal

import pytest
from lxml import etree

from efactura import anaf
from efactura.models import Invoice
from efactura.ubl import NS_CBC, build_xml
from tests.samples import pfa_invoice

live = pytest.mark.skipif(os.environ.get("EFACTURA_OFFLINE") == "1", reason="offline")


def test_totals_non_vat():
    inv = pfa_invoice(vat_payer=False)
    assert inv.net_total == Decimal("6499.99")
    assert inv.tax_total == Decimal("0.00")
    assert inv.gross_total == Decimal("6499.99")


def test_totals_vat():
    inv = pfa_invoice(vat_payer=True)
    assert inv.tax_total == Decimal("1365.00")  # 6499.99 * 21%, rounded
    assert inv.gross_total == Decimal("7864.99")


def test_non_vat_invoice_has_no_vat_ids():
    xml = build_xml(pfa_invoice(vat_payer=False))
    root = etree.fromstring(xml)
    ids = [e.text for e in root.iter(f"{{{NS_CBC}}}CompanyID")]
    assert not any(i.startswith("RO") for i in ids)
    assert b"VATEX-EU-O" in xml


def test_roundtrip_dict():
    inv = pfa_invoice(vat_payer=True)
    again = Invoice.from_dict(inv.to_dict())
    assert build_xml(again) == build_xml(inv)


@live
@pytest.mark.parametrize("vat_payer", [False, True])
def test_anaf_accepts(vat_payer):
    ok, messages = anaf.validate(build_xml(pfa_invoice(vat_payer)))
    assert ok, messages


@live
def test_anaf_pdf():
    assert anaf.to_pdf(build_xml(pfa_invoice())).startswith(b"%PDF")
