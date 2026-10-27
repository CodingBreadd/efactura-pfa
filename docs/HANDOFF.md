# Handoff

## State (2026-10-27)
- Released: v0.2.0 (exe), v0.3.0 (storno + EUR), v0.4.0 (edit/delete rejected). https://github.com/CodingBreadd/efactura-pfa/releases
- **Phase 5a (v0.5.0)**, branch `phase5-foreign-customers`: customers can be outside Romania.
  - `Party.country` (ISO alpha-2, default RO). Abroad, `county` holds a free-text region and `cui` the foreign VAT or registration id.
  - **ANAF quirk:** the buyer legal id (BT-47) must be numeric, otherwise "ERRIdentif: nu a fost identificat cui cumparator".
    Non-residents get `0000000000000` there. The real id goes in PartyIdentification (BT-46) and, for AE, PartyTaxScheme (BT-48).
    Digits-only would pass too, but SPV routes by that number and could hit a real Romanian CUI.
  - VAT regime (VAT payers only, invoice-wide): S / AE (reverse charge, needs the buyer's VAT id) / O (outside the EU).
    The form picks it from the country and the VAT checkbox and fills in a suggested note (`VAT_NOTES`). Non-VAT payers are always O.
  - All 5 foreign variants pass live ANAF. The form JS was exercised in jsdom (country switch, regime, note, rate lock).
- Next: Phase 5b, an app icon (.ico for the exe plus a favicon) and polish (friendly HTML error pages instead of JSON).

## Phase 4 notes (v0.4.0)
- `draft`/`invalid` invoices can be edited (number fixed) or deleted (the latest returns its number). `valid` ones get a storno only.
  "Am încărcat-o în SPV" sets `sent`. Originals show "Stornată prin X". Duplicate numbers give a 400.

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
- Tests: `pytest`, 34 passing (offline mode: `EFACTURA_OFFLINE=1`)

## Next steps (in order)
1. Darius: post `docs/ANNOUNCE.md` to r/programare, r/Romania and PFA groups to find SPV testers.
2. SPV OAuth: register the app on anaf.ro, get client_id/secret, add a redirect handler, store tokens.
   Needs a tester with a certificate.
3. Pull received invoices (listaMesajeFactura + descarcare) into the archive. Needs SPV.
4. Nice to have: an app icon (.ico) for the exe, and code signing to avoid the SmartScreen warning.

Why this project: no open-source e-Factura tool for PFAs exists (anafpy is transport only;
Odoo modules are paid; PilotFisc/facturamea are closed), and SPV purges after ~60 days.
Work through branches and PRs; ask Darius before merging.
