#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y ca-certificates curl software-properties-common zstd python3-venv python3-pip postgresql-common
add-apt-repository -y universe
install -d /usr/share/postgresql-common/pgdg
curl --fail --silent --show-error https://www.postgresql.org/media/keys/ACCC4CF8.asc \
  -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
cat >/etc/apt/sources.list.d/pgdg.sources <<'EOF'
Types: deb
URIs: https://apt.postgresql.org/pub/repos/apt
Suites: noble-pgdg
Architectures: arm64
Components: main
Signed-By: /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
EOF
apt-get update
apt-get install -y caddy postgresql-18

id -u form >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin form
install -d -o form -g form /opt/form-store
systemctl enable --now postgresql
if ! sudo -u postgres psql -Atc "SELECT 1 FROM pg_roles WHERE rolname='form'" | grep -q 1; then
  sudo -u postgres createuser form
fi
if ! sudo -u postgres psql -Atc "SELECT 1 FROM pg_database WHERE datname='tgdd_products'" | grep -q 1; then
  sudo -u postgres createdb -O form tgdd_products
fi
fallocate -l 1G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >>/etc/fstab
touch /var/lib/form-bootstrap-ready
