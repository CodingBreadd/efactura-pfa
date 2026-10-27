# Handoff

## State (2026-10-27): Phase 2 (Windows .exe) in PR, not merged yet
- Branch `phase2-windows-exe` holds the PyInstaller build plus CI. Merge it, then tag `v0.2.0` to publish the release.
- `efactura-pfa.spec`: one-file console exe, 24 MB. Built and smoke-tested locally on Python 3.14:
  settings, invoice creation, live ANAF validation, PDF, and the XML archive all work.
- `.github/workflows/build.yml`: on PRs and pushes it runs the offline tests, builds the exe,
  smoke-tests it and uploads it as an artifact. On a `v*` tag it attaches the exe to a GitHub release.
- The exe stores data in `Documents\e-Factura PFA` (the real Documents folder via SHGetFolderPathW,
  so OneDrive redirection works). `EFACTURA_DATA` overrides it. The settings page shows the path.
- A second launch only reopens the browser (the port is already taken). `EFACTURA_NO_BROWSER=1` is for CI.
- `docs/ANNOUNCE.md`: draft Romanian post asking for testers. Darius posts it himself.

## v0.1 (merged on main)
- `efactura/models.py`: Invoice/Party/Line plus totals (Decimal, HALF_UP)
- `efactura/ubl.py`: CIUS-RO UBL XML. **Passes ANAF validation** for categories O and S.
- `efactura/anaf.py`: `validate` and `to_pdf` use public endpoints, no auth, both tested live.
  `SpvClient` (upload/status/list/download) is written from the docs but **untested**.
- `efactura/store.py`: SQLite plus XML files in `<data>/arhiva/<year>/`
- `efactura/app.py`: FastAPI and Jinja UI in Romanian. `python -m efactura` serves port 8765.
- Tests: `pytest`, 9 passing (offline mode: `EFACTURA_OFFLINE=1`)

## Next steps (in order)
1. Merge the PR, then `git tag v0.2.0 && git push --tags`, then check that the release has the exe.
2. Post `docs/ANNOUNCE.md` to r/programare, r/Romania and PFA groups to find SPV testers.
3. Phase 3: credit notes (InvoiceTypeCode 381) and EUR invoices (TaxCurrencyCode RON plus a second TaxTotal).
4. UI: edit or delete drafts; invoices are currently immutable once created.
5. SPV OAuth: register the app on anaf.ro, get client_id/secret, add a redirect handler, store tokens.
   Needs a tester with a certificate.
6. Pull received invoices (listaMesajeFactura + descarcare) into the archive.
7. Nice to have: an app icon (.ico) for the exe, and code signing to avoid the SmartScreen warning.

Why this project: no open-source e-Factura tool for PFAs exists (anafpy is transport only;
Odoo modules are paid; PilotFisc/facturamea are closed), and SPV purges after ~60 days.
Work through branches and PRs; ask Darius before merging.
