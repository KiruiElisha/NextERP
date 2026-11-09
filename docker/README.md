# Local ERPNext (Docker) — v16

Run a full ERPNext **v16** site on this computer with the `nexterp` app installed. The desktop app
can start this stack automatically (Sign in → **Set up local ERPNext**, or Settings → Local Docker).
You can also run it from the command line.

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/macOS) or Docker Engine + Compose (Linux)
- About 4 GB RAM free for the first start (image pull + site create)

## From the desktop app (recommended)

1. Install and start **Docker Desktop**.
2. Open **ERPNext** desktop.
3. On first launch (or Sign in → **Set up local ERPNext**), the app pulls ERPNext v16, starts
   containers, creates the site, and installs `nexterp`.
4. Sign in with `http://localhost:8000` / `Administrator` / `admin` (default).

Progress is shown on the sign-in screen; Settings → Local Docker can repair or restart the stack.

## From the command line

```bash
cd docker
cp .env.example .env          # optional: change passwords / port
docker compose up -d
```

Then create the site and install apps (once):

```bash
# Linux / macOS
chmod +x scripts/bootstrap.sh && ./scripts/bootstrap.sh

# Windows (PowerShell)
.\scripts\bootstrap.ps1
```

Default image: `frappe/erpnext:v16.54.0` (`ERPNEXT_VERSION` in `.env`).

## Day to day

```bash
docker compose up -d      # start
docker compose down       # stop (keeps data)
docker compose logs -f backend
```

## Backup

```bash
docker compose exec backend bench --site localhost backup --with-files
```

Two-way live merging with a cloud site is not supported.
