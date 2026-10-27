# Handoff

## State (2026-10-27)
- Released: v0.2.0 (Windows exe), v0.3.0 (storno + EUR/USD/GBP). See https://github.com/CodingBreadd/efactura-pfa/releases
- **Phase 4 (v0.4.0)**, branch `phase4-edit-delete`: invoices in status `draft`/`invalid` can be edited
  (number fixed, archive file moved if the year changes) or deleted (deleting the latest gives its number back,
  and the confirmation warns about the gap otherwise). `valid` invoices only get a storno. "Am încărcat-o în SPV"
  sets `sent` and locks the invoice for good. Originals show "Stornată prin X". Duplicate numbers give a 400 instead of a 500.

## Phase 3 notes (v0.3.0)
- Storno = UBL `CreditNote` (type 381), positive amounts, `BillingReference` to the original. No DueDate, no PaymentMeans.
  In the list the `total` column is stored negative for credit notes (it also drives the "storno" badge).
- EUR/USD/GBP: `TaxCurrencyCode RON` plus a second `TaxTotal` in RON (BR-RO-030 / BR-53), and a Note with the rate.
- `efactura/bnr.py`: rates from `curs.bnr.ro` (the old www.bnr.ro XML URLs redirect to the homepage). Uses the last rate
  published strictly before the invoice date (Codul fiscal art. 290). Namespace differs 2025 (http) vs 2026 (https).
- ANAF: credit notes use the `FCN` standard for validation and PDF, `CN` for the SPV upload. All 8 variants pass live.

## Phase 2 notes
- `efactura-pfa.spec`: one-file console exe. `.github/workflows/build.yml` runs the tests, builds and smoke-tests the exe on PRs and pushes, and on a `v*` tag attaches it to a release.
- The exe stores data in `Documents\e-Factura PFA` (real Documents folder via SHGetFolderPathW). `EFACTURA_DATA` overrides it.
- `docs/ANNOUNCE.md`: draft Romanian post asking for testers. Darius posts it himself.

## v0.1 (merged on main)
- `efactura/models.py`: Invoice/Party/Line plus totals (Decimal, HALF_UP)
- `efactura/ubl.py`: CIUS-RO UBL XML. **Passes ANAF validation** for categories O and S.
- `efactura/anaf.py`: `validate` and `to_pdf` use public endpoints, no auth, both tested live.
  `SpvClient` (upload/status/list/download) is written from the docs but **untested**.
- `efactura/store.py`: SQLite plus XML files in `<data>/arhiva/<year>/`
- `efactura/app.py`: FastAPI and Jinja UI in Romanian. `python -m efactura` serves port 8765.
- Tests: `pytest`, 25 passing (offline mode: `EFACTURA_OFFLINE=1`)

## Next steps (in order)
1. Darius: post `docs/ANNOUNCE.md` to r/programare, r/Romania and PFA groups to find SPV testers.
2. Foreign customers: non-RO country, no county code, foreign VAT id (common for freelancers billing EU/US clients).
3. SPV OAuth: register the app on anaf.ro, get client_id/secret, add a redirect handler, store tokens.
   Needs a tester with a certificate.
4. Pull received invoices (listaMesajeFactura + descarcare) into the archive. Needs SPV.
5. Nice to have: an app icon (.ico) for the exe, and code signing to avoid the SmartScreen warning.

Why this project: no open-source e-Factura tool for PFAs exists (anafpy is transport only;
Odoo modules are paid; PilotFisc/facturamea are closed), and SPV purges after ~60 days.
Work through branches and PRs; ask Darius before merging.
