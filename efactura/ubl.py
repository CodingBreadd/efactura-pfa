"""Render an Invoice as UBL 2.1 XML following the Romanian CIUS-RO rules.

A storno is a UBL CreditNote (type 381) with positive amounts that references the
original invoice. Element order matters: the UBL schema is a strict sequence.
"""
from __future__ import annotations

from decimal import Decimal
from lxml import etree

from .models import Invoice, Party

NS_INV = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
NS_CN = "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"

CUSTOMIZATION_ID = "urn:cen.eu:en16931:2017#compliant#urn:efactura.mfinante.ro:CIUS-RO:1.0.1"


def _cac(parent, tag):
    return etree.SubElement(parent, f"{{{NS_CAC}}}{tag}")


def _cbc(parent, tag, text, **attrs):
    el = etree.SubElement(parent, f"{{{NS_CBC}}}{tag}", **attrs)
    el.text = str(text)
    return el


def _amount(parent, tag, value: Decimal, currency: str):
    return _cbc(parent, tag, f"{value:.2f}", currencyID=currency)


def _rate(rate: Decimal) -> str:
    return f"{Decimal(rate).normalize():f}"


def _party(parent, party: Party, with_vat_id: bool):
    p = _cac(parent, "Party")
    addr = _cac(p, "PostalAddress")
    _cbc(addr, "StreetName", party.street)
    _cbc(addr, "CityName", party.city)
    _cbc(addr, "CountrySubentity", f"RO-{party.county}")
    _cbc(_cac(addr, "Country"), "IdentificationCode", "RO")
    if with_vat_id and party.vat_id:
        ts = _cac(p, "PartyTaxScheme")
        _cbc(ts, "CompanyID", party.vat_id)
        _cbc(_cac(ts, "TaxScheme"), "ID", "VAT")
    le = _cac(p, "PartyLegalEntity")
    _cbc(le, "RegistrationName", party.name)
    _cbc(le, "CompanyID", party.cui)
    if party.email:
        _cbc(_cac(p, "Contact"), "ElectronicMail", party.email)


def _tax_category(parent, tag, category: str, rate: Decimal, with_reason: bool):
    tc = _cac(parent, tag)
    _cbc(tc, "ID", category)
    if category == "S":
        _cbc(tc, "Percent", _rate(rate))
    elif with_reason and category == "O":
        _cbc(tc, "TaxExemptionReasonCode", "VATEX-EU-O")
    _cbc(_cac(tc, "TaxScheme"), "ID", "VAT")


def build_xml(inv: Invoice) -> bytes:
    cur = inv.currency
    doc, ns = ("CreditNote", NS_CN) if inv.credit_note else ("Invoice", NS_INV)
    # EN 16931 rule BR-O-02/04: "not subject to VAT" invoices carry no VAT ids.
    any_o = any(l.vat_category == "O" for l in inv.lines)

    root = etree.Element(f"{{{ns}}}{doc}", nsmap={None: ns, "cac": NS_CAC, "cbc": NS_CBC})
    _cbc(root, "CustomizationID", CUSTOMIZATION_ID)
    _cbc(root, "ID", inv.number)
    _cbc(root, "IssueDate", inv.issue_date.isoformat())
    if inv.due_date and not inv.credit_note:  # a UBL 2.1 CreditNote has no DueDate
        _cbc(root, "DueDate", inv.due_date.isoformat())
    _cbc(root, f"{doc}TypeCode", "381" if inv.credit_note else "380")
    if inv.note:
        _cbc(root, "Note", inv.note)
    if cur != "RON":
        rate = f"{Decimal(inv.exchange_rate):.4f}".replace(".", ",")
        _cbc(root, "Note", f"Curs BNR: 1 {cur} = {rate} RON")
    _cbc(root, "DocumentCurrencyCode", cur)
    if cur != "RON":  # BR-RO-030: VAT is always accounted in RON
        _cbc(root, "TaxCurrencyCode", "RON")
    if inv.ref_number:
        ref = _cac(_cac(root, "BillingReference"), "InvoiceDocumentReference")
        _cbc(ref, "ID", inv.ref_number)
        if inv.ref_date:
            _cbc(ref, "IssueDate", inv.ref_date.isoformat())

    _party(_cac(root, "AccountingSupplierParty"), inv.supplier, with_vat_id=not any_o)
    _party(_cac(root, "AccountingCustomerParty"), inv.customer, with_vat_id=not any_o)

    if inv.supplier.iban and not inv.credit_note:
        pm = _cac(root, "PaymentMeans")
        _cbc(pm, "PaymentMeansCode", "30")  # credit transfer
        acc = _cac(pm, "PayeeFinancialAccount")
        _cbc(acc, "ID", inv.supplier.iban.replace(" ", ""))
        if inv.supplier.bank:
            _cbc(acc, "Name", inv.supplier.bank)

    tt = _cac(root, "TaxTotal")
    _amount(tt, "TaxAmount", inv.tax_total, cur)
    for g in inv.tax_groups():
        st = _cac(tt, "TaxSubtotal")
        _amount(st, "TaxableAmount", g["taxable"], cur)
        _amount(st, "TaxAmount", g["tax"], cur)
        _tax_category(st, "TaxCategory", g["category"], g["rate"], with_reason=True)
    if cur != "RON":  # BR-53: the VAT total again, in the tax currency
        _amount(_cac(root, "TaxTotal"), "TaxAmount", inv.tax_total_ron, "RON")

    lmt = _cac(root, "LegalMonetaryTotal")
    _amount(lmt, "LineExtensionAmount", inv.net_total, cur)
    _amount(lmt, "TaxExclusiveAmount", inv.net_total, cur)
    _amount(lmt, "TaxInclusiveAmount", inv.gross_total, cur)
    _amount(lmt, "PayableAmount", inv.gross_total, cur)

    for i, line in enumerate(inv.lines, start=1):
        il = _cac(root, f"{doc}Line")
        _cbc(il, "ID", i)
        _cbc(il, "CreditedQuantity" if inv.credit_note else "InvoicedQuantity",
             _rate(line.quantity), unitCode=line.unit)
        _amount(il, "LineExtensionAmount", line.amount, cur)
        item = _cac(il, "Item")
        _cbc(item, "Name", line.name)
        _tax_category(item, "ClassifiedTaxCategory", line.vat_category, line.vat_rate, with_reason=False)
        _amount(_cac(il, "Price"), "PriceAmount", Decimal(line.unit_price), cur)

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
