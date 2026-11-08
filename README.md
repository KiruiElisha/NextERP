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
| `nexterp/` | Frappe app for the server. Sync API, home summary, quick entry and the ESG door. Requires ERPNext; the ESG screens appear when the ESG app (`ghg`) is on the site too. |
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

## A new site from the app

"No site yet? Create one on Nergaa Cloud" on the sign-in screen signs up or signs in to Nergaa Cloud with an
emailed code, creates a site with the apps the user picks (plus `nexterp`), finishes ERPNext's setup wizard
with the company name and the password they chose, then signs in to it. The server side is
`nergaa_cloud/desktop.py` in nergaa-cloud; `NERGAA_CLOUD=https://…` points the app at another Press.

## The assistant

Overview → Assistant answers questions about the business from the site's records and drafts
documents (a quotation, an order, a payment) that open unsaved in the normal form to be checked and
saved. A System Manager turns it on in **NextERP Settings**: Claude (Anthropic), OpenAI, Gemini,
Groq or any OpenAI-style server, including a local one (Ollama, LM Studio, vLLM), with who may use
it and a daily limit per user. The server does everything (`nexterp/api/ai.py`): the model reads
only through `frappe.get_list` and `has_permission` as the signed-in user, never saves, and the key
never leaves the site. Conversations are kept in the app's memory only.

## KRA eTIMS

With the etims_oscu app on the site, every sales invoice is
signed by KRA, and the app shows it: the invoice has a KRA eTIMS panel (signed, queued or failed, the CU
invoice number and the QR the buyer scans), with **Send to KRA now** for one that isn't signed; the till's
receipt carries the CU serial and invoice numbers, internal data, signature and QR, waiting the few
seconds KRA takes to sign. Without etims_oscu nothing changes (`nexterp/api/etims.py`).

## First steps and the keyboard

A new site's Home shows **Get set up**: add items and a customer, make the first sale, invite the team,
connect M-Pesa, the assistant and eTIMS, each step opening the screen where it's done and ticked off as
the site records it. **Ctrl K** goes anywhere: every screen, **New …** for each document the user may
create, every report, the documents on the computer, and (three words or more) the assistant.

## Languages

Settings → Language sets the user's own language, the same User.language Desk uses, from the languages
the site has turned on. The app's words come from Frappe's translations of every installed app
(ERPNext's labels and messages included), NextERP's own (`nexterp/translations/<lang>.csv`, Swahili
included), then the site's Translation records, which a System Manager adds or corrects in Desk.
Server messages follow the same setting. Arabic and other right-to-left languages turn the layout
around; numbers, dates and "5 minutes ago" are written the language's way. The words are kept on the
computer, so the app opens in the user's language offline. The Swahili file was written for this app:
have a native speaker review it, and add a language by adding its CSV (or Translation records).

## Drafts while offline

When the site can't be reached, a new document (an invoice, a quotation, a customer) can still be
started and saved: it is kept on the computer and saved on the site, as a draft, after the next sync
that reaches it. The top bar says how many are waiting; **Waiting to send** lists them.

- Only new documents, only drafts. Submitting needs the site; nothing kept offline is ever submitted.
- The site saves each with the user's own permissions and ERPNext's validation, and works out prices
  and totals then. A draft it refuses stays, with the reason, to fix and send again.
- Each draft has an id; the site remembers the ids it has saved (NextERP Outbox Receipt), so a send
  retried after a lost answer, or a draft reopened and saved while it was being sent, never makes two.
- Drafts are kept per user: signing out, or another person signing in, never sends, shows or drops
  them; they go when their owner signs in again. At most 500 per user, 1 MB each.
- A new form opens offline from the last one the site gave; dates it had are moved to today.

## Server setup

```bash
bench get-app https://github.com/KiruiElisha/ghg
bench get-app https://github.com/KiruiElisha/NextERP
bench --site <site> install-app nexterp   # after erpnext; install ghg first for the ESG screens
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
