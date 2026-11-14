"""Aplicación FastAPI principal para "Las dos caras de la lluvia" (GPCP, MERRA-2 y GPM IMERG vía OPeNDAP)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.api.rutas import analisis, catalogo, datos
from core.config import obtener_ajustes
from core.motor.datos import DatosNoDisponibles, inventario_cache
from core.motor.series import SerieRechazada
from core.servicios.consultas import obtener_catalogo, obtener_datasets


def _credenciales_configuradas() -> dict[str, bool]:
    env_ok = bool(os.environ.get("EARTHDATA_USERNAME") and os.environ.get("EARTHDATA_PASSWORD"))
    home = Path.home()
    netrc_ok = (home / ".netrc").exists() or (home / "_netrc").exists()
    return {"variables_entorno": env_ok, "netrc": netrc_ok, "listo": env_ok or netrc_ok}


def crear_app() -> FastAPI:
    ajustes = obtener_ajustes()
    app = FastAPI(
        title="NASA Space Apps — Las Dos Caras de la Lluvia API (OPeNDAP en Memoria)",
        description=(
            "API REST con **OPeNDAP en memoria RAM (0 archivos NetCDF/HDF en disco)** para consultar los datasets "
            "de NASA **GPCP mensual (v3.3)**, **MERRA-2 (v5.12.4)** y **GPM IMERG Final (v07)**, calcular anomalías, "
            "extremos de lluvia (CDD, R20mm, W, PRCPTOT, SDII), tendencias estadísticas con corrección por "
            "autocorrelación (OLS + n efectivo y Mann-Kendall Hamed-Rao) y mapas por píxel para consumo del frontend."
        ),
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    origenes = list(ajustes.cors_origins) or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origenes,
        allow_credentials=origenes != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DatosNoDisponibles)
    async def _error_datos_no_disponibles(_req: Request, exc: DatosNoDisponibles) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "error": "datos_no_disponibles_en_memoria",
                "mensaje": str(exc),
                "variable": exc.variable,
                "region": exc.region,
                "periodo": [exc.inicio, exc.fin],
                "sugerencia": (
                    "Pasa ?descargar=true para consultar en vivo por OPeNDAP en memoria RAM, "
                    "envía POST /api/v1/opendap/precargar, o añade ?sintetico=true durante el desarrollo del frontend."
                ),
            },
        )

    @app.exception_handler(SerieRechazada)
    async def _error_serie_rechazada(_req: Request, exc: SerieRechazada) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": "serie_rechazada",
                "mensaje": str(exc),
                "reporte": exc.reporte,
            },
        )

    @app.exception_handler(KeyError)
    async def _error_no_encontrado(_req: Request, exc: KeyError) -> JSONResponse:
        detalle = exc.args[0] if exc.args else str(exc)
        return JSONResponse(
            status_code=404,
            content={"error": "no_encontrado", "mensaje": str(detalle)},
        )

    @app.exception_handler(ValueError)
    async def _error_valor(_req: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"error": "parametro_invalido", "mensaje": str(exc)},
        )

    @app.get("/", tags=["Estado"], summary="Información general de la API")
    def ruta_raiz() -> dict[str, Any]:
        return {
            "nombre": "NASA Space Apps — Las Dos Caras de la Lluvia API",
            "version": "0.2.0",
            "modo_acceso": "opendap_memoria_sin_archivos",
            "documentacion": "/docs",
            "prefijo_api": "/api/v1",
            "datasets": list(obtener_datasets().keys()),
            "variables": list(obtener_catalogo().keys()),
        }

    @app.get("/api/v1/salud", tags=["Estado"], summary="Estado del servidor, caché en RAM y credenciales OPeNDAP")
    def ruta_salud() -> dict[str, Any]:
        cat = obtener_catalogo()
        ds = obtener_datasets()
        entradas_ram = inventario_cache()
        return {
            "estado": "ok",
            "modo_acceso": "opendap_memoria",
            "almacenamiento_disco": False,
            "n_datasets": len(ds),
            "n_variables": len(cat),
            "cubos_en_memoria_ram": len(entradas_ram),
            "kb_en_memoria_ram": round(sum(float(i.get("kb_ram", 0.0)) for i in entradas_ram), 2),
            "max_cubos_ram": obtener_ajustes().cache_memoria_max,
            "credenciales_earthdata": _credenciales_configuradas(),
        }

    app.include_router(catalogo.router, prefix="/api/v1")
    app.include_router(analisis.router, prefix="/api/v1")
    app.include_router(datos.router, prefix="/api/v1")

    # Endpoints raíz directos especificados en la guía "Down to Earth" (§05)
    app.add_api_route(
        "/catalog",
        catalogo.ruta_catalogo_down_to_earth,
        methods=["GET"],
        tags=["Down to Earth (4 Variables)"],
        summary="Catálogo Down to Earth (GET /catalog)",
    )
    app.add_api_route(
        "/demo/result",
        analisis.ruta_demo_result_dte,
        methods=["GET"],
        tags=["Down to Earth (4 Variables)"],
        summary="Resultado completo Down to Earth (GET /demo/result)",
    )
    app.add_api_route(
        "/demo/csv/{frecuencia}",
        analisis.ruta_demo_csv_dte,
        methods=["GET"],
        tags=["Down to Earth (4 Variables)"],
        summary="Exportación CSV mensual/anual Down to Earth en memoria",
    )
    return app


app = crear_app()
