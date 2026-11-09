#!/usr/bin/env bash
# Create the local site (once) and install erpnext + nexterp.
# Run from the docker/ folder after `docker compose up -d`.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
	# shellcheck disable=SC1091
	set -a && source .env && set +a
fi

SITE="${SITE_NAME:-localhost}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"
DB_PASSWORD="${MYSQL_ROOT_PASSWORD:-admin}"
PORT="${HTTP_PORT:-8000}"

echo "Local ERPNext bootstrap (ERPNext v16 + nexterp)"
echo "Waiting for backend…"
for _ in $(seq 1 60); do
	if docker compose exec -T backend bench --version >/dev/null 2>&1; then
		break
	fi
	sleep 2
done

if ! docker compose exec -T backend bench --version >/dev/null 2>&1; then
	echo "Backend is not ready. Run: docker compose up -d" >&2
	exit 1
fi

# Ensure nexterp is listed (bind mount) and apps.txt is current.
docker compose exec -T backend bash -c 'ls -1 apps > sites/apps.txt'

if docker compose exec -T backend test -f "sites/${SITE}/site_config.json"; then
	echo "Site ${SITE} already exists."
else
	echo "Creating site ${SITE}…"
	docker compose exec -T backend bench new-site "${SITE}" \
		--mariadb-root-password "${DB_PASSWORD}" \
		--admin-password "${ADMIN_PASSWORD}" \
		--no-mariadb-socket \
		--install-app erpnext
fi

echo "Installing nexterp…"
docker compose exec -T backend bench --site "${SITE}" install-app nexterp || true

# Point the site at the published address (desktop Sign-in uses this host).
docker compose exec -T backend bench --site "${SITE}" set-config host_name "http://localhost:${PORT}"
docker compose exec -T backend bench use "${SITE}"

if [[ "${INSTALL_GHG:-0}" == "1" ]]; then
	GHG_GIT="${GHG_GIT:-https://github.com/KiruiElisha/ghg}"
	echo "Installing ESG app from ${GHG_GIT}…"
	docker compose exec -T backend bench get-app "${GHG_GIT}" || true
	docker compose exec -T backend bench --site "${SITE}" install-app ghg || true
fi

echo
echo "Local ERPNext is ready."
echo "  URL:      http://localhost:${PORT}"
echo "  User:     Administrator"
echo "  Password: ${ADMIN_PASSWORD}"
echo
echo "In the desktop app, sign in with site address: http://localhost:${PORT}"
echo "Cloud sync/backup stays separate — back up with:"
echo "  docker compose exec backend bench --site ${SITE} backup --with-files"
