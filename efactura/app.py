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

EDITABLE = {"draft", "invalid"}
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
               exchange_rate="", ref=None, note="", action="/factura/noua", editing=False)
    return render(request, "new.html", **(ctx | prefill))


def _form_lines(inv: Invoice) -> list[dict]:
    return [{"name": l.name, "qty": str(l.quantity), "unit": l.unit, "price": str(l.unit_price),
             "rate": str(l.vat_rate)} for l in inv.lines]


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
    return _invoice_form(request, customer=inv.customer.__dict__, lines=_form_lines(inv), currency=inv.currency,
                         exchange_rate=str(inv.exchange_rate or ""),
                         ref={"number": inv.number, "date": inv.issue_date.isoformat()})


@app.get("/curs")
def exchange_rate(moneda: str, data: str):
    try:
        published, rate = bnr.rate_for(moneda, date.fromisoformat(data))
    except (httpx.HTTPError, LookupError, ValueError, SyntaxError) as e:
        raise HTTPException(502, f"Cursul BNR nu e disponibil: {e}")
    return {"rate": str(rate), "date": published.isoformat()}


def _invoice_from_form(form, number: str) -> Invoice:
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
        inv = Invoice(number=number.strip(), issue_date=date.fromisoformat(form["issue_date"]),
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
    return inv


def _check(xml: bytes) -> tuple[str, list[str]]:
    try:
        ok, messages = anaf.validate(xml)
        return ("valid" if ok else "invalid"), messages
    except httpx.HTTPError as e:
        return "draft", [f"Validarea ANAF nu a răspuns: {e}"]


@app.post("/factura/noua")
async def create_invoice(request: Request):
    form = await request.form()
    inv = _invoice_from_form(form, form.get("number") or "")
    if store.find_id(inv.number):
        raise HTTPException(400, f"Numărul {inv.number} există deja.")
    xml = build_xml(inv)
    invoice_id = store.save_invoice(inv, xml, *_check(xml))
    if inv.number == store.next_number():
        store.bump_number()
    return RedirectResponse(f"/factura/{invoice_id}", status_code=303)


def _editable_row(invoice_id: int):
    """Only invoices ANAF hasn't accepted can change. Valid ones get a storno instead."""
    row = _row(invoice_id)
    if row["status"] not in EDITABLE:
        raise HTTPException(400, "Factura e deja validă. Pentru corecturi emite o factură storno.")
    return row


@app.get("/factura/{invoice_id}/editeaza", response_class=HTMLResponse)
def edit_form(request: Request, invoice_id: int):
    inv = Invoice.from_dict(json.loads(_editable_row(invoice_id)["data"]))
    ref = {"number": inv.ref_number, "date": inv.ref_date.isoformat() if inv.ref_date else ""}
    return _invoice_form(request, number=inv.number, today=inv.issue_date.isoformat(),
                         due=inv.due_date.isoformat() if inv.due_date else "", note=inv.note,
                         customer=inv.customer.__dict__, lines=_form_lines(inv), currency=inv.currency,
                         exchange_rate=str(inv.exchange_rate or ""), ref=ref if inv.credit_note else None,
                         action=f"/factura/{invoice_id}/editeaza", editing=True)


@app.post("/factura/{invoice_id}/editeaza")
async def edit_invoice(request: Request, invoice_id: int):
    row = _editable_row(invoice_id)
    inv = _invoice_from_form(await request.form(), row["number"])  # the number never changes
    xml = build_xml(inv)
    store.update_invoice(invoice_id, inv, xml, *_check(xml))
    return RedirectResponse(f"/factura/{invoice_id}", status_code=303)


@app.post("/factura/{invoice_id}/sterge")
def delete_invoice(invoice_id: int):
    _editable_row(invoice_id)
    store.delete_invoice(invoice_id)
    return RedirectResponse("/", status_code=303)


@app.post("/factura/{invoice_id}/incarcata")
def mark_uploaded(invoice_id: int):
    """The user uploaded the XML to SPV by hand: lock it like a sent invoice."""
    row = _row(invoice_id)
    if row["status"] != "valid":
        raise HTTPException(400, "Doar o factură validă se încarcă în SPV.")
    store.update_status(invoice_id, "sent", json.loads(row["messages"]))
    return RedirectResponse(f"/factura/{invoice_id}", status_code=303)


@app.get("/factura/{invoice_id}", response_class=HTMLResponse)
def show_invoice(request: Request, invoice_id: int):
    row = _row(invoice_id)
    inv = Invoice.from_dict(json.loads(row["data"]))
    ref_id = store.find_id(inv.ref_number) if inv.ref_number else None
    return render(request, "show.html", row=row, inv=inv, messages=json.loads(row["messages"]),
                  ref_id=ref_id, credit_notes=store.credit_notes_for(inv.number),
                  editable=row["status"] in EDITABLE,
                  is_last=row["number"] == store.number(store.get("next_number", 1) - 1))


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
