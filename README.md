# NextERP

ERPNext as a fast desktop app, with ESG built in. Installs as **ERPNext**.

The desktop app keeps the data people look up all day (customers, suppliers, items, prices,
invoices, orders, payments) in a local database on the computer, synced in the background. Lists,
search and lookups answer from that cache, so they are instant and still work when the network is
slow. Every posting still goes to the ERPNext server, which stays the one source of truth for
stock, numbering and the ledger.

## What is in this repository

| Path | What it is |
|---|---|
| `nexterp/` | Frappe app for the server. Sync API, home summary, quick entry and the ESG door. Requires ERPNext and the ESG app (`ghg`). |
| `desktop/core/` | Rust library. The local SQLite cache with full-text search, the Frappe HTTP client and the sync engine. No UI, so it is tested on its own. |
| `desktop/src-tauri/` | The Tauri shell: the window, the menu, and the commands the UI calls. |
| `desktop/ui/` | The interface: Vue 3, Vite and Tailwind, bundled into the app so it opens without waiting on the server. |

## How it works

```
 desktop/ui (Vue)  --invoke-->  src-tauri (commands)  -->  core
                                                           |-- store: SQLite + FTS5 on the computer
                                                           |-- client: HTTP to the ERPNext site
                                                           '-- sync: nexterp.api.sync.changes, page by page
```

- **Reads** come from the local cache. A full document is fetched when you open it, and stored.
- **Sync** asks the server for rows changed since the last sync of each doctype, only those the
  user may read, and removes deleted ones. It runs on sign-in, every few minutes, and on demand.
- **Writes** go to the server with the user's own permissions; the changed doctype syncs right after.
- **Anything without a native screen** opens in ERPNext's own Desk, in a window of the app.
- **The site** can be a cloud site or ERPNext running locally (for example in Docker): the app signs
  in to whatever address it is given.

## Server setup

```bash
bench get-app https://github.com/KiruiElisha/ghg
bench get-app https://github.com/KiruiElisha/NextERP
bench --site <site> install-app nexterp   # installs after erpnext and ghg
```

## Desktop development

```bash
cd desktop
npm install && npm --prefix ui install
npm run dev                                  # the app, against any ERPNext site with nexterp installed
cargo test -p nexterp-core --release         # the engine's tests
```

Installers for Windows, macOS and Linux are built by `.github/workflows/release-desktop.yml`.

## Speed, measured

On a cache of 50,000 items (`desktop/core/tests/store.rs`): full-text search in about 5 ms, a
filtered and sorted page in about 50 ms. In the running app, search answers in 2 ms and a list of
invoices in about 25 ms including the hop from the window to the engine. The whole interface is
about 47 KB gzipped and is bundled into the app.

## Running ERPNext on the computer

The app signs in to any address, so it works the same against a cloud site or a local one
(`http://localhost:8000`, for example ERPNext in Docker). Keeping a local site and a cloud site
in step is a separate problem: see the roadmap.

## Roadmap

1. **More native screens**, chosen by what people open most: payments and receipts, purchase
   invoices, stock entries and stock balance, the report centre. Everything else already opens in
   Desk inside the app.
2. **Stock and prices that stay current**: bins and price changes in the sync, so quick entry
   can warn about stock before saving.
3. **A drafts outbox**: invoices started offline are kept on the computer and saved to the site
   when it is back. Postings themselves still happen on the server.
4. **Local site alongside the cloud**: ERPNext in Docker on the computer or the office network,
   for speed and for working through outages. Recommended order: first a read-only local copy
   kept up to date from the cloud (the cloud stays the only place documents are posted); only
   then, if needed, a branch site that posts its own documents and sends them to the cloud as
   whole documents. Two-way merging of one ERPNext database is not planned: stock levels,
   numbering and the ledger cannot be merged safely.
5. **Signed installers and auto-update** for Windows and macOS.

## Tests

```bash
bench --site <site> run-tests --app nexterp
```

## Licence

GPL v3, as Frappe and ERPNext are.
