#!/usr/bin/env bash
#===============================================================================
#  LAMP Stack Auto-Installer for Ubuntu 24.04 LTS
#  Installs: Apache2, MariaDB, PHP 8.x + common modules
#  Usage:    sudo bash deb_lamp.sh
#  Non-interactive: DB_ROOT_PASS='secret' sudo bash deb_lamp.sh
#===============================================================================
set -euo pipefail

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${GREEN}[✔]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✘]${NC} $1"; exit 1; }
info() { echo -e "${CYAN}[i]${NC} $1"; }

# ── Pre-flight checks ─────────────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && err "This script must be run as root. Use: sudo bash $0"

info "Starting LAMP installation on Ubuntu 24.04..."
echo ""

# ── MariaDB root password ─────────────────────────────────────────────────────
# Accept from environment variable (non-interactive/SSH mode) OR prompt if
# running in a real terminal. Fails fast if neither provides a value.
if [[ -n "${DB_ROOT_PASS:-}" ]]; then
    info "Using DB_ROOT_PASS from environment."
elif [[ -t 0 ]]; then
    read -sp "$(echo -e "${CYAN}[?]${NC} Set MariaDB root password: ")" DB_ROOT_PASS
    echo ""
else
    err "No DB_ROOT_PASS set and no TTY available.
  Run with:  DB_ROOT_PASS='yourpassword' sudo bash $0"
fi
[[ -z "${DB_ROOT_PASS:-}" ]] && err "Password cannot be empty."

# ── 1. Update system ──────────────────────────────────────────────────────────
info "Updating package lists..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq
log "System updated."

# ── 2. Install Apache ─────────────────────────────────────────────────────────
info "Installing Apache2..."
apt-get install -y -qq apache2
systemctl enable --now apache2
log "Apache2 installed and running."

a2enmod rewrite headers ssl
systemctl restart apache2
log "Apache modules enabled: rewrite, headers, ssl."

# ── 3. Install MariaDB ────────────────────────────────────────────────────────
info "Installing MariaDB..."
apt-get install -y -qq mariadb-server mariadb-client
systemctl enable --now mariadb
log "MariaDB installed and running."

info "Securing MariaDB..."
mariadb -u root <<SQLEOF
ALTER USER 'root'@'localhost' IDENTIFIED BY '${DB_ROOT_PASS}';
DELETE FROM mysql.user WHERE User='';
DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1');
DROP DATABASE IF EXISTS test;
DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%';
FLUSH PRIVILEGES;
SQLEOF
log "MariaDB secured."

# ── 4. Install PHP ────────────────────────────────────────────────────────────
info "Installing PHP and common modules..."
apt-get install -y -qq \
    php \
    libapache2-mod-php \
    php-mysql \
    php-cli \
    php-curl \
    php-gd \
    php-mbstring \
    php-xml \
    php-zip \
    php-intl \
    php-bcmath \
    php-json
log "PHP installed."

# ── 5. Configure Apache to prefer PHP ────────────────────────────────────────
info "Configuring Apache to prefer index.php..."
cat > /etc/apache2/mods-enabled/dir.conf <<'DIREOF'
<IfModule mod_dir.c>
    DirectoryIndex index.php index.html index.cgi index.pl index.xhtml index.htm
</IfModule>
DIREOF
systemctl restart apache2
log "Apache configured to serve PHP first."

# ── 6. Create PHP info test page ──────────────────────────────────────────────
info "Creating test page at /var/www/html/info.php..."
cat > /var/www/html/info.php <<'PHPEOF'
<?php
// LAMP Stack Test Page - DELETE THIS IN PRODUCTION
phpinfo();
PHPEOF
log "Test page created."

# ── 7. Configure UFW firewall ─────────────────────────────────────────────────
info "Configuring UFW firewall..."
ufw allow OpenSSH      >/dev/null 2>&1
ufw allow "Apache Full" >/dev/null 2>&1
ufw --force enable     >/dev/null 2>&1
log "Firewall configured (SSH + HTTP/HTTPS allowed)."

# ── 8. Security headers ───────────────────────────────────────────────────────
info "Adding security headers to Apache..."
cat > /etc/apache2/conf-available/security-headers.conf <<'SECEOF'
<IfModule mod_headers.c>
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-Frame-Options "SAMEORIGIN"
    Header always set X-XSS-Protection "1; mode=block"
    Header always set Referrer-Policy "strict-origin-when-cross-origin"
</IfModule>
SECEOF
a2enconf security-headers
systemctl restart apache2
log "Security headers enabled."

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  LAMP Stack Installation Complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Apache:   $(apache2 -v 2>/dev/null | head -1 | awk '{print $3}')"
echo -e "  MariaDB:  $(mariadb --version 2>/dev/null | awk '{print $5}' | tr -d ',')"
echo -e "  PHP:      $(php -v 2>/dev/null | head -1 | awk '{print $2}')"
echo ""
echo -e "  Web Root:    /var/www/html/"
echo -e "  Test Page:   http://$(hostname -I | awk '{print $1}')/info.php"
echo ""
echo -e "${YELLOW}  ⚠  Remember to delete /var/www/html/info.php in production!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"