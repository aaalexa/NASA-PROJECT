#!/usr/bin/env sh
set -eu

# Si se inyectan EARTHDATA_USERNAME y EARTHDATA_PASSWORD en el contenedor,
# genera ~/.netrc en memoria de sesión con permisos 0600 para earthaccess/OPeNDAP.
if [ -n "${EARTHDATA_USERNAME:-}" ] && [ -n "${EARTHDATA_PASSWORD:-}" ]; then
    NETRC_PATH="${HOME}/.netrc"
    cat > "${NETRC_PATH}" <<EOF
machine urs.earthdata.nasa.gov
    login ${EARTHDATA_USERNAME}
    password ${EARTHDATA_PASSWORD}
EOF
    chmod 0600 "${NETRC_PATH}"
fi

exec "$@"

