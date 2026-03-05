#!/usr/bin/env bash
# deploy/provision.sh
#
# One-time setup for a fresh Digital Ocean Ubuntu droplet.
# Run as root once. Everything after this is handled by GitHub Actions.
#
# Usage:
#   scp deploy/provision.sh root@YOUR_DROPLET_IP:/tmp/
#   ssh root@YOUR_DROPLET_IP "bash /tmp/provision.sh"

set -euo pipefail

echo "═══════════════════════════════════════"
echo " ConnectionSphere Factory — Provisioning"
echo "═══════════════════════════════════════"

# ── System packages ───────────────────────────────────────────────────────────
apt-get update -q
apt-get install -y --no-install-recommends \
    git curl nginx graphviz postgresql redis-server \
    python3-certbot-nginx ufw

# ── Deploy user ───────────────────────────────────────────────────────────────
if ! id deploy &>/dev/null; then
    useradd -m -s /bin/bash deploy
    echo "deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart factory" \
        >> /etc/sudoers.d/deploy-factory
fi

# ── UV ────────────────────────────────────────────────────────────────────────
sudo -u deploy bash -c \
    'curl -LsSf https://astral.sh/uv/install.sh | sh'

# ── PostgreSQL ────────────────────────────────────────────────────────────────
systemctl enable postgresql
systemctl start postgresql

sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='factory_user'" \
    | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER factory_user WITH PASSWORD '${DB_PASSWORD:?DB_PASSWORD not set}';"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='factory'" \
    | grep -q 1 || \
    sudo -u postgres createdb factory --owner=factory_user

echo "PostgreSQL: factory database ready"

# ── Redis ─────────────────────────────────────────────────────────────────────
systemctl enable redis-server
systemctl start redis-server
echo "Redis: running on localhost:6379"

# ── App directory ─────────────────────────────────────────────────────────────
mkdir -p /app
chown deploy:deploy /app

sudo -u deploy bash -c '
    cd /app
    if [ ! -d .git ]; then
        git clone https://github.com/martinhewing/connectionsphere-factory .
    fi
    uv python pin 3.12
    uv sync --frozen --no-dev
'

# ── Environment file ──────────────────────────────────────────────────────────
if [ ! -f /app/.env ]; then
    cp /app/.env.example /app/.env
    echo ""
    echo "  /app/.env created from .env.example"
    echo "  Edit it now: nano /app/.env"
    echo "  Set ANTHROPIC_API_KEY, CARTESIA_API_KEY, and FACTORY_API_KEY before starting"
fi
chown deploy:deploy /app/.env
chmod 600 /app/.env

# ── Systemd service ───────────────────────────────────────────────────────────
cp /app/deploy/factory.service /etc/systemd/system/factory.service
systemctl daemon-reload
systemctl enable factory

# ── Nginx ─────────────────────────────────────────────────────────────────────
cat > /etc/nginx/sites-available/factory << 'NGINX'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass         http://127.0.0.1:8391;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/factory /etc/nginx/sites-enabled/factory
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# ── Firewall ──────────────────────────────────────────────────────────────────
ufw --force enable
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp

# ── GitHub Actions SSH key ────────────────────────────────────────────────────
mkdir -p /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
touch /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh

echo ""
echo "═══════════════════════════════════════"
echo " Provisioning complete."
echo ""
echo " Next steps:"
echo " 1. Edit /app/.env — set ANTHROPIC_API_KEY, CARTESIA_API_KEY, FACTORY_API_KEY"
echo " 2. Add your GitHub Actions SSH public key to:"
echo "    /home/deploy/.ssh/authorized_keys"
echo " 3. Set GitHub secrets:"
echo "    DO_HOST        = $(curl -s ifconfig.me)"
echo "    DO_USER        = deploy"
echo "    DO_SSH_KEY     = (your Actions private key)"
echo "    PRODUCTION_URL = http://$(curl -s ifconfig.me)"
echo " 4. systemctl start factory"
echo " 5. curl http://localhost:8391/health"
echo "═══════════════════════════════════════"
