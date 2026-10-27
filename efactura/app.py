"""Local web UI. Run with: python -m efactura"""
from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from . import anaf, bnr
from .models import COUNTIES, CURRENCIES, UNITS, VAT_CATEGORIES, Invoice, Line, Party
from .store import Store
from .ubl import build_xml

app = FastAPI(title="e-Factura PFA")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
store = Store()

PARTY_FIELDS = ("name", "cui", "street", "city", "county", "reg_com", "iban", "bank", "email")


def render(request: Request, name: str, **ctx):
    ctx.update(counties=COUNTIES, units=UNITS, vat_categories=VAT_CATEGORIES, currencies=CURRENCIES)
    return templates.TemplateResponse(request, name, ctx)


def _party_from_form(form, prefix: str) -> Party:
    data = {f: (form.get(f"{prefix}_{f}") or "").strip() for f in PARTY_FIELDS}
    data["cui"] = data["cui"].upper().removeprefix("RO").strip()
    return Party(vat_payer=form.get(f"{prefix}_vat_payer") == "on", **data)


@app.get("/", response_class=HTMLResponse)
def index(request: Request, q: str = ""):
    if not store.get("supplier"):
        return RedirectResponse("/setari", status_code=303)
    return render(request, "index.html", invoices=store.list_invoices(q), q=q)


@app.get("/setari", response_class=HTMLResponse)
def settings_page(request: Request):
    return render(request, "settings.html", s=store.get("supplier", {}),
                  series=store.get("series", "PFA"), next_number=store.get("next_number", 1),
                  data_dir=store.dir.resolve())


@app.post("/setari")
async def settings_save(request: Request):
    form = await request.form()
    supplier = _party_from_form(form, "s")
    store.set("supplier", supplier.__dict__)
    store.set("series", (form.get("series") or "PFA").strip())
    store.set("next_number", int(form.get("next_number") or 1))
    return RedirectResponse("/", status_code=303)


def _invoice_form(request: Request, **prefill):
    today = date.today()
    ctx = dict(number=store.next_number(), today=today.isoformat(),
               due=(today + timedelta(days=14)).isoformat(), supplier=store.get("supplier"),
               customers=store.customers(), customer={}, lines=[], currency="RON",
               exchange_rate="", ref=None)
    return render(request, "new.html", **(ctx | prefill))


@app.get("/factura/noua", response_class=HTMLResponse)
def new_invoice(request: Request):
    if not store.get("supplier"):
        return RedirectResponse("/setari", status_code=303)
    return _invoice_form(request)


@app.get("/factura/{invoice_id}/storno", response_class=HTMLResponse)
def credit_note_form(request: Request, invoice_id: int):
    """Prefill a full storno; the user can lower quantities for a partial one."""
    inv = Invoice.from_dict(json.loads(_row(invoice_id)["data"]))
    if inv.credit_note:
        raise HTTPException(400, "O factură storno nu se mai stornează.")
    lines = [{"name": l.name, "qty": str(l.quantity), "unit": l.unit, "price": str(l.unit_price),
              "rate": str(l.vat_rate)} for l in inv.lines]
    return _invoice_form(request, customer=inv.customer.__dict__, lines=lines, currency=inv.currency,
                         exchange_rate=str(inv.exchange_rate or ""),
                         ref={"number": inv.number, "date": inv.issue_date.isoformat()})


@app.get("/curs")
def exchange_rate(moneda: str, data: str):
    try:
        published, rate = bnr.rate_for(moneda, date.fromisoformat(data))
    except (httpx.HTTPError, LookupError, ValueError, SyntaxError) as e:
        raise HTTPException(502, f"Cursul BNR nu e disponibil: {e}")
    return {"rate": str(rate), "date": published.isoformat()}


@app.post("/factura/noua")
async def create_invoice(request: Request):
    form = await request.form()
    supplier = Party(**store.get("supplier"))
    vat_payer = supplier.vat_payer
    try:
        lines = []
        for name, qty, price, unit, rate in zip(form.getlist("line_name"), form.getlist("line_qty"),
                                                form.getlist("line_price"), form.getlist("line_unit"),
                                                form.getlist("line_rate")):
            if not name.strip():
                continue
            lines.append(Line(name=name.strip(), quantity=Decimal(qty.replace(",", ".")),
                              unit_price=Decimal(price.replace(",", ".")), unit=unit,
                              vat_category="S" if vat_payer else "O",
                              vat_rate=Decimal(rate or "0") if vat_payer else Decimal("0")))
        if not lines:
            raise ValueError("Adaugă cel puțin o linie.")
        credit = form.get("credit_note") == "1"
        currency = form.get("currency") or "RON"
        if currency not in CURRENCIES:
            raise ValueError(f"monedă necunoscută {currency}")
        rate = None
        if currency != "RON":
            rate = Decimal((form.get("exchange_rate") or "0").replace(",", "."))
            if rate <= 0:
                raise ValueError("completează cursul BNR")
        inv = Invoice(number=form["number"].strip(), issue_date=date.fromisoformat(form["issue_date"]),
                      due_date=date.fromisoformat(form["due_date"]) if form.get("due_date") and not credit else None,
                      supplier=supplier, customer=_party_from_form(form, "c"),
                      lines=lines, note=(form.get("note") or "").strip(),
                      currency=currency, exchange_rate=rate, credit_note=credit,
                      ref_number=(form.get("ref_number") or "").strip(),
                      ref_date=date.fromisoformat(form["ref_date"]) if form.get("ref_date") else None)
        if credit and not inv.ref_number:
            raise ValueError("storno fără factura de referință")
    except (ValueError, InvalidOperation, KeyError) as e:
        raise HTTPException(400, f"Date invalide: {e}")

    xml = build_xml(inv)
    try:
        ok, messages = anaf.validate(xml)
        status = "valid" if ok else "invalid"
    except httpx.HTTPError as e:
        status, messages = "draft", [f"Validarea ANAF nu a răspuns: {e}"]
    invoice_id = store.save_invoice(inv, xml, status, messages)
    if inv.number == store.next_number():
        store.bump_number()
    return RedirectResponse(f"/factura/{invoice_id}", status_code=303)


@app.get("/factura/{invoice_id}", response_class=HTMLResponse)
def show_invoice(request: Request, invoice_id: int):
    row = _row(invoice_id)
    inv = Invoice.from_dict(json.loads(row["data"]))
    ref_id = store.find_id(inv.ref_number) if inv.ref_number else None
    return render(request, "show.html", row=row, inv=inv, messages=json.loads(row["messages"]),
                  ref_id=ref_id)


@app.post("/factura/{invoice_id}/valideaza")
def revalidate(invoice_id: int):
    row = _row(invoice_id)
    try:
        ok, messages = anaf.validate(row["xml"])
        store.update_status(invoice_id, "valid" if ok else "invalid", messages)
    except httpx.HTTPError as e:
        store.update_status(invoice_id, row["status"], [f"Validarea ANAF nu a răspuns: {e}"])
    return RedirectResponse(f"/factura/{invoice_id}", status_code=303)


@app.get("/factura/{invoice_id}/xml")
def download_xml(invoice_id: int):
    row = _row(invoice_id)
    return Response(row["xml"], media_type="application/xml",
                    headers={"Content-Disposition": f'attachment; filename="{row["number"]}.xml"'})


@app.get("/factura/{invoice_id}/pdf")
def download_pdf(invoice_id: int):
    row = _row(invoice_id)
    try:
        pdf = anaf.to_pdf(row["xml"])
    except (httpx.HTTPError, ValueError) as e:
        raise HTTPException(502, f"ANAF nu a generat PDF-ul: {e}")
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{row["number"]}.pdf"'})


def _row(invoice_id: int):
    row = store.get_invoice(invoice_id)
    if not row:
        raise HTTPException(404, "Factura nu există.")
    return row
