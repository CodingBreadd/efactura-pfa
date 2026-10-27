# Handoff

## State (2026-10-27): v0.1 done
- `efactura/models.py`: Invoice/Party/Line plus totals (Decimal, HALF_UP)
- `efactura/ubl.py`: CIUS-RO UBL XML. **Passes ANAF validation** for categories O and S.
- `efactura/anaf.py`: `validate` and `to_pdf` use public endpoints, no auth, both tested live.
  `SpvClient` (upload/status/list/download) is written from the docs but **untested**.
- `efactura/store.py`: SQLite at `data/efactura.db` plus XML files in `data/arhiva/<year>/`
- `efactura/app.py`: FastAPI and Jinja UI in Romanian. `python -m efactura` serves port 8765.
- Tests: `pytest`, 8 passing (offline mode: `EFACTURA_OFFLINE=1`)

## Recommended order
Phase 2 = Windows .exe (PyInstaller) attached to a GitHub release, then post it to
Romanian freelancer communities (r/programare, r/Romania, PFA groups) and ask for
testers with a certificate for SPV. Then credit notes + EUR invoices.
Why this project: no open-source e-Factura tool for PFAs exists (anafpy is transport
only; Odoo modules are paid; PilotFisc/facturamea are closed), and SPV purges after ~60 days.
Work through branches + PRs from now on; ask before merging.

## Known gaps / next steps
1. Published: https://github.com/CodingBreadd/efactura-pfa (public, main)
2. SPV OAuth flow: register the app on anaf.ro, get client_id/secret, add a
   redirect handler in app.py, and store tokens. Needs a tester with a certificate.
3. Credit notes (InvoiceTypeCode 381), EUR invoices (need TaxCurrencyCode RON and a second TaxTotal).
4. Pull received invoices (listaMesajeFactura + descarcare) into the archive.
5. PyInstaller .exe for non-technical users.
6. UI: allow editing or deleting drafts; currently invoices are immutable once created.
