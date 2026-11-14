# syntax=docker/dockerfile:1
FROM debian:bookworm-slim AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/opt/python

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    build-essential \
    pkg-config \
    libhdf5-dev \
    libnetcdf-dev \
    libgeos-dev \
    libproj-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Instalar Python 3.15 administrado por uv
RUN uv python install 3.15

# Copiar metadatos primero para aprovechar la caché de capas de Docker
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

# Sincronizar dependencias bloqueadas e instalar el paquete del proyecto + generar wheel en dist/
RUN uv sync --frozen --no-dev && uv build


# ==============================================================================
# Etapa final de ejecución (imagen limpia para producción en api.moody-trends.earth)
# ==============================================================================
FROM debian:bookworm-slim AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_INSTALL_DIR=/opt/python \
    PATH="/app/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    HOME=/home/appuser \
    UVICORN_WORKERS=2

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    passwd \
    libexpat1 \
    libglib2.0-0 \
    libstdc++6 \
    zlib1g \
    libhdf5-103-1 \
    libhdf5-hl-100 \
    libnetcdf19 \
    libgeos-c1v5 \
    libproj25 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --create-home --shell /bin/sh appuser

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /opt/python /opt/python
COPY --from=builder --chown=appuser:appuser /app /app
COPY --chown=appuser:appuser pytest.ini ./pytest.ini
COPY --chown=appuser:appuser tests ./tests
COPY --chown=appuser:appuser entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chmod +x /usr/local/bin/entrypoint.sh \
    && python -c "import netCDF4, h5netcdf, rasterio, rasterio.features, geopandas, regionmask, statsmodels; print('Native C extensions OK')"

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/v1/salud || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["sh", "-c", "uvicorn core.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2} --proxy-headers --forwarded-allow-ips='*'"]

