# Handoff

## State (2026-10-27)
- **v0.2.0 released**: https://github.com/CodingBreadd/efactura-pfa/releases/tag/v0.2.0 (Windows exe, built by CI)
- **Phase 3 (v0.3.0)**, branch `phase3-storno-eur`:
  - Storno = UBL `CreditNote` (type 381), positive amounts, `BillingReference` to the original invoice.
    No DueDate and no PaymentMeans. Use the "Stornează" button on an invoice page; quantities can be lowered for a partial storno.
    In the list, the `total` column is stored negative for credit notes (it also drives the "storno" badge).
  - EUR/USD/GBP: `TaxCurrencyCode RON` plus a second `TaxTotal` in RON (BR-RO-030 / BR-53). A Note carries the rate.
  - `efactura/bnr.py`: rates from `curs.bnr.ro` (the old www.bnr.ro XML URLs now redirect to the homepage).
    Uses the last rate published strictly before the invoice date (Codul fiscal art. 290).
    The namespace differs between the 2025 (http) and 2026 (https) files, so parsing matches on local names.
  - ANAF: validation and PDF use the `FCN` standard for credit notes and `FACT1` for invoices. SPV upload uses `CN` / `UBL`.
  - All 8 variants (invoice/storno x RON/EUR x VAT/non-VAT) pass live ANAF validation.

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
- Tests: `pytest`, 23 passing (offline mode: `EFACTURA_OFFLINE=1`)

## Next steps (in order)
1. Darius: post `docs/ANNOUNCE.md` to r/programare, r/Romania and PFA groups to find SPV testers.
2. Foreign customers: non-RO country, no county code, foreign VAT id (common for freelancers billing EU/US clients).
3. UI: edit or delete drafts and invalid invoices (currently immutable). Show "stornată de X" on the original.
4. SPV OAuth: register the app on anaf.ro, get client_id/secret, add a redirect handler, store tokens.
   Needs a tester with a certificate.
5. Pull received invoices (listaMesajeFactura + descarcare) into the archive. Needs SPV.
6. Nice to have: an app icon (.ico) for the exe, and code signing to avoid the SmartScreen warning.

Why this project: no open-source e-Factura tool for PFAs exists (anafpy is transport only;
Odoo modules are paid; PilotFisc/facturamea are closed), and SPV purges after ~60 days.
Work through branches and PRs; ask Darius before merging.
