# NextERP: notes for anyone working here

ERPNext as a fast desktop app, ESG built in. Installs and shows as **ERPNext**. See README.md for
the architecture.

## Rules that shape the design

- **The server decides.** Every posting (invoice, payment, stock) goes to the ERPNext site with the
  user's own permissions. The local cache is for reading: never post from it, never invent numbers
  in it. Offline writes, if they come, are a queued outbox for drafts only.
- **Read from the cache, fresh from the site.** Lists, search and pickers query the local SQLite
  store. A screen that needs the site shows the cached answer first (`cachedThenFresh`) and
  replaces it when the fresh one arrives.
- **Stay upstream-compatible.** No fork of Frappe or ERPNext, and nothing that patches them. Server
  code lives in the `nexterp` app; use APIs that work on Frappe 15 and 16. Plain field names only in
  `order_by` (newer Frappe rejects SQL expressions there).
- **What is cached is the server's call.** `nexterp/manifest.py` lists the doctypes and fields;
  `desktop/ui/src/lib/doctypes.js` only says how they look.
- **Speed is a feature with numbers.** Keep the 50,000-item test in `desktop/core/tests/store.rs`
  under 100 ms for search, and keep the UI bundle small (no chart or UI kit libraries for things a
  few lines of SVG or Tailwind do).

## Layout

- `nexterp/`: Frappe app (Python, tabs, ruff). APIs in `nexterp/api/`, tests in `nexterp/tests/`.
- `desktop/core/`: Rust engine without UI (store, client, sync). Unit tests in `src`, store tests and
  live tests in `tests/`.
- `desktop/src-tauri/`: the shell. `commands.rs` is everything the UI can call.
- `desktop/ui/`: Vue 3 + Vite + Tailwind. Talks to Rust only through `src/lib/backend.js`.

## Running things

```bash
bench --site <site> run-tests --app nexterp            # server, needs erpnext + ghg on the site
cd desktop && cargo test -p nexterp-core --release     # engine
NEXTERP_TEST_SITE=http://site:8000 NEXTERP_TEST_USER=… NEXTERP_TEST_PASSWORD=… \
  cargo test -p nexterp-core --release --test live     # engine against a real site
cd desktop && npm install && npm --prefix ui install && npm run dev   # the app
```

## Style

- Python: tabs, `ruff check` and `ruff format`. Small functions; docstrings say why.
- Rust: `cargo fmt`. Errors go through `nexterp_core::Error` so the UI can tell signed-out,
  refused and offline apart.
- Vue: `<script setup>`, Tailwind classes, the `card`/`btn-*`/`input` components in `style.css`.
- Tests: names that say what broke; real records and a real site over mocks.
- Commits: Conventional Commits with a scope, sentence case (`feat(sync): Send deletions`), and a
  short body saying why.
