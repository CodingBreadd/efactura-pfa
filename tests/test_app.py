import importlib
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
