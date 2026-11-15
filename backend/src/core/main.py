"""Punto de entrada de la API FastAPI y CLI de "Las dos caras de la lluvia".

Ejecutar servidor de desarrollo:
    uvicorn core.main:app --reload --port 8000
    # o bien:
    nasa-project servir --port 8000 --reload

Consultar catálogo validado en consola:
    nasa-project catalogo

Descargar y recortar datos de NASA Earthdata a data/cache:
    nasa-project descargar --variable lluvia_gpcp --region sahel --inicio 2001-01 --fin 2024-12

Análisis Down to Earth con datos reales (P, T, SM, ET) y resultados en disco (lee backend/.env):
    nasa-project dte --region corredor_seco_centroamericano --salida resultados/dte/corredor_seco_centroamericano
"""
from __future__ import annotations

import argparse
import json
import sys

from core.config import cargar_dotenv

# Local runs (`uvicorn core.main:app`, `nasa-project …`): read backend/.env before the app reads its settings.
# Never overrides variables already set (Docker / docker compose provide them and the image has no .env).
cargar_dotenv()

import uvicorn  # noqa: E402

from core.api.app import app, crear_app  # noqa: E402
from core.config import PERIODO_COMUN
from core.motor.datos import descargar_variable
from core.servicios.consultas import consultar_datasets, obtener_catalogo
from core.servicios.regiones import resolver_region

__all__ = ["app", "crear_app", "main"]


def _cmd_servir(args: argparse.Namespace) -> int:
    uvicorn.run(
        "core.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


def _cmd_catalogo(_args: argparse.Namespace) -> int:
    datos = consultar_datasets()
    print(json.dumps(datos, indent=2, ensure_ascii=False))
    return 0


def _cmd_descargar(args: argparse.Namespace) -> int:
    catalogo = obtener_catalogo()
    if args.variable not in catalogo:
        print(f"Error: variable '{args.variable}' desconocida. Válidas: {sorted(catalogo)}", file=sys.stderr)
        return 1
    reg = resolver_region(args.region, args.bbox)

    def _progreso(actual: int, total: int, msg: str) -> None:
        print(f"[{actual}/{total}] {msg}", flush=True)

    res = descargar_variable(
        args.variable,
        reg.id,
        reg.bbox,
        args.inicio,
        args.fin,
        catalogo,
        progreso=_progreso,
        forzar=args.forzar,
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


def _cmd_dte(args: argparse.Namespace) -> int:
    from pathlib import Path

    from core.servicios.dte_cli import analizar_desde_csv, cargar_env, ejecutar_dte_real, escribir_salidas

    if not args.region and not args.bbox and not args.desde_csv:
        print("Error: indica --region o --bbox (o --desde-csv).", file=sys.stderr)
        return 1
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    salida = Path(args.salida)
    if args.desde_csv:
        res = analizar_desde_csv(
            Path(args.desde_csv), region=args.region, bbox=args.bbox, inicio=args.inicio, fin=args.fin, alfa=args.alfa
        )
        escribir_salidas(res, salida)
    else:
        cargadas = cargar_env(Path(args.env) if args.env else None)
        if cargadas:
            print(f"Variables cargadas desde .env: {', '.join(cargadas)}")
        res = ejecutar_dte_real(
            region=args.region, bbox=args.bbox, inicio=args.inicio, fin=args.fin, salida=salida, alfa=args.alfa
        )
    print(f"\nResultados en {salida.resolve()}")
    tr = res["metadata"].get("trend_span")
    if tr:
        print(f"Tramo de tendencias: {tr['start']}–{tr['end']} ({tr['n_years']} años)")
    for cod in ("P", "T", "SM", "ET"):
        print(" -", res["variables"][cod]["summary_text"])
    for par in res["joint"]["pairs_list"]:
        print(" -", par["summary_text"])
    for w in res["metadata"].get("warnings", []):
        print(" !", w)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="nasa-project",
        description="Backend y API REST para consultar GPCP, MERRA-2 y GPM IMERG (NASA Earthdata).",
    )
    sub = parser.add_subparsers(dest="comando")

    p_srv = sub.add_parser("servir", help="Levanta el servidor HTTP FastAPI con Uvicorn.")
    p_srv.add_argument("--host", default="127.0.0.1", help="Host de escucha (por defecto 127.0.0.1).")
    p_srv.add_argument("--port", type=int, default=8000, help="Puerto de escucha (por defecto 8000).")
    p_srv.add_argument("--reload", action="store_true", help="Recarga automática al editar el código.")

    sub.add_parser("catalogo", help="Imprime en JSON los datasets y variables validados.")

    p_desc = sub.add_parser("descargar", help="Descarga y recorta una variable de NASA Earthdata a data/cache.")
    p_desc.add_argument("--variable", required=True, help="Id de la variable en catalogo.yaml.")
    p_desc.add_argument("--region", default="sahel", help="Id de región predefinida o slug.")
    p_desc.add_argument("--bbox", type=float, nargs=4, metavar=("OESTE", "SUR", "ESTE", "NORTE"))
    p_desc.add_argument("--inicio", default=PERIODO_COMUN[0], help="Mes inicial AAAA-MM.")
    p_desc.add_argument("--fin", default=PERIODO_COMUN[1], help="Mes final AAAA-MM.")
    p_desc.add_argument("--forzar", action="store_true", help="Ignorar caché existente.")

    p_dte = sub.add_parser(
        "dte",
        help="Análisis Down to Earth con datos reales (P, T, SM, ET) y escritura de resultados en disco.",
    )
    p_dte.add_argument("--region", default=None, help="Id de región predefinida (regiones.yaml).")
    p_dte.add_argument("--bbox", type=float, nargs=4, metavar=("OESTE", "SUR", "ESTE", "NORTE"))
    p_dte.add_argument("--inicio", default="2001-01", help="Mes inicial AAAA-MM (por defecto 2001-01).")
    p_dte.add_argument("--fin", default="2024-12", help="Mes final AAAA-MM (por defecto 2024-12).")
    p_dte.add_argument("--alfa", type=float, default=0.05, help="Nivel de significancia fijado de antemano.")
    p_dte.add_argument("--salida", required=True, help="Carpeta donde escribir resultados.json y los CSV.")
    p_dte.add_argument("--env", default=None, help="Ruta a un .env con EARTHDATA_* (por defecto backend/.env).")
    p_dte.add_argument(
        "--desde-csv", default=None,
        help="Reanaliza una serie regional ya guardada (serie_regional.csv) sin descargar nada.",
    )

    args = parser.parse_args(argv)
    if args.comando == "dte":
        return _cmd_dte(args)
    if args.comando == "catalogo":
        return _cmd_catalogo(args)
    if args.comando == "descargar":
        return _cmd_descargar(args)
    if args.comando == "servir":
        return _cmd_servir(args)

    # Si se invoca sin subcomando, levanta el servidor por defecto en 127.0.0.1:8000.
    ns = argparse.Namespace(host="127.0.0.1", port=8000, reload=False)
    return _cmd_servir(ns)


if __name__ == "__main__":
    sys.exit(main())

