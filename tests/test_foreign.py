import os
from dataclasses import replace
from decimal import Decimal

import pytest
from lxml import etree

from efactura import anaf
from efactura.models import VAT_NOTES, Party
from efactura.ubl import NS_CAC, NS_CBC, NON_RESIDENT_ID, build_xml
from tests.samples import credit_note, eur, pfa_invoice

live = pytest.mark.skipif(os.environ.get("EFACTURA_OFFLINE") == "1", reason="offline")
C, B = f"{{{NS_CAC}}}", f"{{{NS_CBC}}}"

DE = Party(name="Kunde GmbH", cui="DE123456789", street="Hauptstr. 1", city="Berlin", county="",
           country="DE", vat_payer=True)
US = Party(name="Client Inc", cui="", street="1 Main St", city="New York", county="NY", country="US")


def abroad(inv, customer, category):
    lines = [replace(l, vat_category=category, vat_rate=Decimal("0")) for l in inv.lines]
    return replace(inv, customer=customer, lines=lines, note=VAT_NOTES.get(category, ""))


SAMPLES = {
    "non-VAT PFA, US client": lambda: abroad(eur(pfa_invoice(False)), US, "O"),
    "non-VAT PFA, DE client": lambda: abroad(eur(pfa_invoice(False)), DE, "O"),
    "reverse charge, DE": lambda: abroad(eur(pfa_invoice(True)), DE, "AE"),
    "reverse charge storno, DE": lambda: abroad(eur(credit_note(True)), DE, "AE"),
    "VAT payer, US client": lambda: abroad(eur(pfa_invoice(True)), US, "O"),
}


def test_vat_ids():
    assert DE.vat_id == "DE123456789"
    assert replace(DE, cui="123456789").vat_id == "DE123456789"
    assert replace(DE, cui="094259216", country="GR").vat_id == "EL094259216"
    assert replace(DE, vat_payer=False).vat_id == "" and US.vat_id == ""


def test_foreign_buyer_xml():
    root = etree.fromstring(build_xml(SAMPLES["reverse charge, DE"]()))
    buyer = root.find(f"{C}AccountingCustomerParty/{C}Party")
    assert buyer.findtext(f"{C}PartyIdentification/{B}ID") == "DE123456789"
    assert buyer.findtext(f"{C}PartyTaxScheme/{B}CompanyID") == "DE123456789"
    assert buyer.findtext(f"{C}PartyLegalEntity/{B}CompanyID") == NON_RESIDENT_ID
    assert buyer.findtext(f"{C}PostalAddress/{C}Country/{B}IdentificationCode") == "DE"
    assert buyer.find(f"{C}PostalAddress/{B}CountrySubentity") is None
    cat = root.find(f"{C}TaxTotal/{C}TaxSubtotal/{C}TaxCategory")
    assert [cat.findtext(f"{B}{t}") for t in ("ID", "Percent", "TaxExemptionReasonCode")] == \
        ["AE", "0", "VATEX-EU-AE"]


@live
@pytest.mark.parametrize("name", SAMPLES)
def test_anaf_accepts_foreign(name):
    ok, messages = anaf.validate(build_xml(SAMPLES[name]()))
    assert ok, messages
