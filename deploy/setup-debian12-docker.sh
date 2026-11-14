#!/usr/bin/env bash
# ==============================================================================
# Script de instalación de Docker Engine + Docker Compose v2 en Debian 12 (Bookworm)
# Para la VM de Azure que aloja https://api.moody-trends.earth
#
# Uso en la VM de Azure (Debian 12):
#   chmod +x deploy/setup-debian12-docker.sh
#   sudo ./deploy/setup-debian12-docker.sh
# ==============================================================================
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Ejecuta este script con sudo: sudo ./deploy/setup-debian12-docker.sh" >&2
    exit 1
fi

echo "==> [1/5] Actualizando paquetes base de Debian 12 (Bookworm)..."
apt-get update
apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    git \
    ufw

echo "==> [2/5] Configurando repositorio oficial de Docker para Debian..."
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

. /etc/os-release
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
  ${VERSION_CODENAME:-bookworm} stable" > /etc/apt/sources.list.d/docker.list

echo "==> [3/5] Instalando Docker Engine, CLI, Buildx y Docker Compose plugin..."
apt-get update
apt-get install -y --no-install-recommends \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin

systemctl enable --now docker

USUARIO_OBJETIVO="${SUDO_USER:-}"
if [ -n "${USUARIO_OBJETIVO}" ] && id "${USUARIO_OBJETIVO}" >/dev/null 2>&1; then
    echo "==> [4/5] Añadiendo al usuario '${USUARIO_OBJETIVO}' al grupo docker..."
    usermod -aG docker "${USUARIO_OBJETIVO}"
fi

echo "==> [5/5] Verificando puertos HTTP/HTTPS (80, 443) y SSH (22) en UFW..."
ufw allow 22/tcp >/dev/null 2>&1 || true
ufw allow 80/tcp >/dev/null 2>&1 || true
ufw allow 443/tcp >/dev/null 2>&1 || true
ufw allow 443/udp >/dev/null 2>&1 || true

echo ""
echo "=============================================================================="
echo "Instalación completada:"
docker --version
docker compose version
echo ""
echo "Pasos siguientes en la VM Azure:"
echo "  1. Cierra sesión y vuelve a entrar (o ejecuta 'newgrp docker')."
echo "  2. Copia .env.example a .env y configura EARTHDATA_USERNAME / EARTHDATA_PASSWORD."
echo "  3. Asegúrate de que el registro DNS tipo A de api.moody-trends.earth apunte a la IP pública de esta VM."
echo "  4. Ejecuta: docker compose up -d --build"
echo "=============================================================================="

