import importlib
from datetime import date
from decimal import Decimal
import os

import pytest
from fastapi.testclient import TestClient

SUPPLIER = {"s_name": "Popescu Ion PFA", "s_cui": "12345674", "s_street": "Str. Memorandumului 10",
            "s_city": "Cluj-Napoca", "s_county": "CJ", "s_iban": "RO49AAAA1B31007593840000",
            "series": "TST", "next_number": "1"}
CUSTOMER = {"c_name": "Client Exemplu SRL", "c_cui": "RO18547290", "c_street": "Bd. Unirii 1",
            "c_city": "SECTOR3", "c_county": "B"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("EFACTURA_DATA", str(tmp_path))
    import efactura.store, efactura.app
    importlib.reload(efactura.store)
    importlib.reload(efactura.app)
    return TestClient(efactura.app.app), tmp_path


@pytest.mark.skipif(os.environ.get("EFACTURA_OFFLINE") == "1", reason="offline")
def test_full_flow(client):
    c, data_dir = client
    assert c.get("/", follow_redirects=False).headers["location"] == "/setari"
    c.post("/setari", data=SUPPLIER)

    form = {"number": "TST0001", "issue_date": "2026-10-27", "due_date": "2026-11-10", **CUSTOMER,
            "line_name": ["Consultanță", "Licență"], "line_qty": ["10", "1"],
            "line_price": ["200,50", "99"], "line_unit": ["HUR", "H87"], "line_rate": ["0", "0"]}
    r = c.post("/factura/noua", data=form)
    assert r.status_code == 200
    assert "validă la ANAF" in r.text, r.text
    assert "2104.00" in r.text  # 10 * 200.50 + 99

    assert (data_dir / "arhiva" / "2026" / "TST0001.xml").exists()
    assert "TST0002" in c.get("/factura/noua").text      # numbering advanced
    assert "Client Exemplu SRL" in c.get("/?q=Exemplu").text
    assert c.get("/factura/1/xml").content.startswith(b"<?xml")


def test_exe_keeps_data_in_documents(monkeypatch):
    import sys
    import efactura.store as store
    monkeypatch.delenv("EFACTURA_DATA", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert store._default_data_dir() == store._documents_dir() / "e-Factura PFA"


def test_eur_invoice_and_storno(client, monkeypatch):
    """Runs offline: ANAF and BNR are stubbed, the XML itself is checked live in test_invoice."""
    import efactura.app
    c, data_dir = client
    monkeypatch.setattr(efactura.app.anaf, "validate", lambda xml: (True, []))
    monkeypatch.setattr(efactura.app.bnr, "rate_for", lambda cur, day: (date(2026, 10, 26), Decimal("5.3467")))
    c.post("/setari", data=SUPPLIER)
    assert c.get("/curs?moneda=EUR&data=2026-10-27").json() == {"rate": "5.3467", "date": "2026-10-26"}

    form = {"number": "TST0001", "issue_date": "2026-10-27", "due_date": "2026-11-10", **CUSTOMER,
            "currency": "EUR", "exchange_rate": "5,3467",
            "line_name": "Consultanță", "line_qty": "10", "line_price": "100", "line_unit": "HUR", "line_rate": "0"}
    assert "Curs BNR: 1 EUR = 5.3467 lei" in c.post("/factura/noua", data=form).text
    assert b"<cbc:TaxCurrencyCode>RON" in c.get("/factura/1/xml").content

    page = c.get("/factura/1/storno").text
    assert 'name="ref_number" value="TST0001"' in page and 'value="Client Exemplu SRL"' in page
    storno = {**form, "number": "TST0002", "credit_note": "1", "ref_number": "TST0001",
              "ref_date": "2026-10-27", "line_qty": "4"}
    r = c.post("/factura/noua", data=storno)
    assert "Factura storno TST0002" in r.text and "400.00" in r.text
    assert c.get("/factura/2/xml").content.count(b"<cbc:CreditNoteTypeCode>381") == 1
    assert c.get("/factura/2/storno").status_code == 400
    assert "-400.00 EUR" in c.get("/").text
