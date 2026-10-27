import os
from decimal import Decimal

import pytest
from lxml import etree

from efactura import anaf
from efactura.models import Invoice
from efactura.ubl import NS_CAC, NS_CBC, NS_CN, build_xml
from tests.samples import credit_note, eur, pfa_invoice

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


def test_credit_note_xml():
    xml = build_xml(credit_note(vat_payer=True))
    root = etree.fromstring(xml)
    assert root.tag == f"{{{NS_CN}}}CreditNote" and anaf.is_credit_note(xml)
    assert root.findtext(f"{{{NS_CBC}}}CreditNoteTypeCode") == "381"
    assert root.findtext(f"{{{NS_CAC}}}BillingReference/{{{NS_CAC}}}InvoiceDocumentReference/{{{NS_CBC}}}ID") == "PFA0001"
    assert len(root.findall(f"{{{NS_CAC}}}CreditNoteLine/{{{NS_CBC}}}CreditedQuantity")) == 2
    assert root.find(f"{{{NS_CBC}}}DueDate") is None and root.find(f"{{{NS_CAC}}}PaymentMeans") is None


def test_eur_has_vat_in_ron():
    inv = eur(pfa_invoice(vat_payer=True))
    assert inv.tax_total_ron == Decimal("7300.98")  # 1365.00 EUR * 5.3487
    root = etree.fromstring(build_xml(inv))
    assert root.findtext(f"{{{NS_CBC}}}TaxCurrencyCode") == "RON"
    totals = [(t.get("currencyID"), t.text) for t in root.findall(f"{{{NS_CAC}}}TaxTotal/{{{NS_CBC}}}TaxAmount")]
    assert totals == [("EUR", "1365.00"), ("RON", "7300.98")]


def test_roundtrip_credit_note_eur():
    inv = eur(credit_note(vat_payer=True))
    assert build_xml(Invoice.from_dict(inv.to_dict())) == build_xml(inv)


SAMPLES = {"invoice": pfa_invoice, "storno": credit_note,
           "eur": lambda v: eur(pfa_invoice(v)), "eur storno": lambda v: eur(credit_note(v))}


@live
@pytest.mark.parametrize("kind", SAMPLES)
@pytest.mark.parametrize("vat_payer", [False, True])
def test_anaf_accepts(kind, vat_payer):
    ok, messages = anaf.validate(build_xml(SAMPLES[kind](vat_payer)))
    assert ok, messages


@live
def test_anaf_pdf():
    assert anaf.to_pdf(build_xml(pfa_invoice())).startswith(b"%PDF")
    assert anaf.to_pdf(build_xml(credit_note())).startswith(b"%PDF")
