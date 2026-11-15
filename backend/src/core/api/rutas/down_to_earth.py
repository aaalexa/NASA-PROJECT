"""Endpoints de cálculo Down to Earth: cálculo exacto desde datos del cliente y trabajos con datos reales de NASA.

Todos usan el mismo motor (`motor/down_to_earth.py` + `motor/limpieza_dte.py`): limpieza estructural, OLS anual +
HAC/Newey–West (rezago 1) + Wald + Holm sobre [P, T, SM, ET] + sensibilidad con rezagos 2 y 3, y análisis conjunto
exploratorio (anomalías z sin estación ni tendencia; Pearson P–SM, T–SM, P–ET).

- POST /down-to-earth/calcular            → calcula desde una serie mensual en JSON (síncrono).
- POST /down-to-earth/calcular/csv        → calcula desde un archivo CSV (síncrono).
- POST /down-to-earth/trabajos            → lanza descarga OPeNDAP + análisis de una región real (202, asíncrono).
- GET  /down-to-earth/trabajos            → lista de trabajos.
- GET  /down-to-earth/trabajos/{id}       → estado y progreso.
- GET  /down-to-earth/trabajos/{id}/resultado        → resultado completo (409 si aún no terminó).
- GET  /down-to-earth/trabajos/{id}/tablas/{tabla}   → mensual | anual | limpieza | diccionario | serie_regional
                                                       (?formato=csv|json).
"""
from __future__ import annotations

import io
from typing import Any, Literal

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import PlainTextResponse

from core.api.esquemas import PeticionCalculoDTE, PeticionTrabajoDTE, ResultadoDTE, TrabajoDTEDTO
from core.motor.datos import validar_periodo
from core.motor.limpieza_dte import tabla_dte, tablas_dte_json
from core.servicios.calculo_dte import calcular_dte_desde_tabla
from core.servicios.trabajos_dte import obtener_gestor_trabajos_dte

router = APIRouter(prefix="/down-to-earth", tags=["Down to Earth (4 Variables)"])

MAX_BYTES_CSV = 5 * 1024 * 1024
TablaDTE = Literal["mensual", "anual", "limpieza", "diccionario", "serie_regional"]


def _con_tablas(resultado: dict[str, Any], incluir: bool) -> dict[str, Any]:
    if incluir:
        resultado["tablas"] = tablas_dte_json(resultado)
    return resultado


@router.post(
    "/calcular",
    response_model=ResultadoDTE,
    summary="Calcula el análisis Down to Earth exacto desde una serie mensual regional (JSON)",
    description=(
        "Recibe la serie mensual regional (fecha, P, T, SM, ET) en unidades finales u originales NASA. Aplica la "
        "limpieza estructural y el método fijo y devuelve el resultado completo con el registro de limpieza. "
        "Los meses faltantes nunca se rellenan con 0 ni se interpolan."
    ),
)
def ruta_calcular_dte(peticion: PeticionCalculoDTE) -> dict[str, Any]:
    df = pd.DataFrame([f.model_dump() for f in peticion.serie])
    resultado = calcular_dte_desde_tabla(
        df, unidades=peticion.unidades, inicio=peticion.inicio, fin=peticion.fin, alfa=peticion.alfa,
        region=peticion.region, simulado=peticion.simulado,
    )
    return _con_tablas(resultado, peticion.incluir_tablas)


@router.post(
    "/calcular/csv",
    response_model=ResultadoDTE,
    summary="Calcula el análisis Down to Earth exacto desde un archivo CSV mensual",
    description=(
        "CSV con columna de fecha (fecha/date/time o anio+mes) y columnas P, T, SM, ET (o los campos NASA "
        "sat_gauge_precip, T2M, SoilMoi0_10cm_inst, Evap_tavg). Separador ',', ';' o tabulador. Máximo 5 MB."
    ),
)
async def ruta_calcular_dte_csv(
    archivo: UploadFile = File(..., description="CSV mensual regional"),
    unidades: Literal["finales", "originales"] = Form("finales"),
    inicio: str = Form("2001-01"),
    fin: str = Form("2024-12"),
    alfa: float = Form(0.05, gt=0.0, lt=0.5),
    region: str | None = Form(None),
    simulado: bool = Form(False),
    incluir_tablas: bool = Form(False),
) -> dict[str, Any]:
    contenido = await archivo.read(MAX_BYTES_CSV + 1)
    if len(contenido) > MAX_BYTES_CSV:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="El CSV supera 5 MB.")
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = contenido.decode("latin-1")
    lineas = [ln for ln in texto.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if not lineas:
        raise ValueError("El CSV está vacío.")
    try:
        df = pd.read_csv(io.StringIO("\n".join(lineas)), sep=None, engine="python", dtype=str)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"No se pudo leer el CSV: {exc}") from exc
    resultado = calcular_dte_desde_tabla(
        df, unidades=unidades, inicio=inicio, fin=fin, alfa=alfa, region=region, simulado=simulado,
    )
    resultado["metadata"]["input"]["file_name"] = archivo.filename
    return _con_tablas(resultado, incluir_tablas)


@router.post(
    "/trabajos",
    response_model=TrabajoDTEDTO,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Lanza el análisis Down to Earth de una región con datos reales de NASA (descarga OPeNDAP + cálculo)",
    description=(
        "Descarga en segundo plano GPCP v3.3 (P), MERRA-2 T2M (T) y GLDAS Noah 2.1 (SM, ET) para la región, aplica "
        "la limpieza y el análisis, y guarda el resultado en memoria. Consulta el progreso con "
        "GET /down-to-earth/trabajos/{id}. Nunca usa datos sintéticos: si falta un producto, el trabajo termina en "
        "'error'. Si ya existe un trabajo con los mismos parámetros (pendiente, ejecutando o completado), se "
        "devuelve ese mismo trabajo salvo que se pida forzar=true."
    ),
)
def ruta_lanzar_trabajo_dte(peticion: PeticionTrabajoDTE) -> dict[str, Any]:
    validar_periodo(peticion.inicio, peticion.fin)
    if not peticion.region and not peticion.bbox:
        raise ValueError("Indica 'region' o 'bbox'.")
    # Con bbox, el nombre de región solo se usa si el cliente lo envió explícitamente (no el valor por defecto),
    # para que la caché quede con la misma clave que usan /analisis y /mapas para esa región personalizada.
    region = peticion.region if (not peticion.bbox or "region" in peticion.model_fields_set) else None
    trabajo = obtener_gestor_trabajos_dte().lanzar(
        region=region, bbox=peticion.bbox,
        inicio=peticion.inicio, fin=peticion.fin, alfa=peticion.alfa, sincrono=peticion.sincrono,
        forzar=peticion.forzar,
    )
    return trabajo.a_dict()


@router.get("/trabajos", summary="Lista los trabajos Down to Earth recientes y en curso")
def ruta_listar_trabajos_dte() -> dict[str, Any]:
    trabajos = obtener_gestor_trabajos_dte().listar()
    return {"total": len(trabajos), "trabajos": trabajos}


@router.get("/trabajos/{trabajo_id}", response_model=TrabajoDTEDTO, summary="Estado y progreso de un trabajo")
def ruta_estado_trabajo_dte(trabajo_id: str) -> dict[str, Any]:
    return obtener_gestor_trabajos_dte().obtener(trabajo_id).a_dict()


def _resultado_listo(trabajo_id: str) -> dict[str, Any]:
    trabajo = obtener_gestor_trabajos_dte().obtener(trabajo_id)
    if trabajo.estado == "error":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail={"error": "trabajo_con_error", "mensaje": trabajo.error})
    if trabajo.estado != "completado" or trabajo.resultado is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail={"error": "trabajo_no_terminado", "estado": trabajo.estado,
                                    "porcentaje": trabajo.porcentaje, "mensaje": trabajo.mensaje})
    return trabajo.resultado


@router.get(
    "/trabajos/{trabajo_id}/resultado",
    response_model=ResultadoDTE,
    summary="Resultado completo de un trabajo terminado (409 si aún no terminó o falló)",
)
def ruta_resultado_trabajo_dte(
    trabajo_id: str,
    incluir_tablas: bool = Query(False, description="Añade las tablas mensual, anual y diccionario con formato."),
) -> dict[str, Any]:
    return _con_tablas(dict(_resultado_listo(trabajo_id)), incluir_tablas)


@router.get(
    "/trabajos/{trabajo_id}/tablas/{tabla}",
    summary="Tabla con formato de un trabajo terminado: mensual, anual, limpieza, diccionario o serie_regional",
    responses={200: {"content": {"text/csv": {}, "application/json": {}}}},
)
def ruta_tabla_trabajo_dte(
    trabajo_id: str,
    tabla: TablaDTE,
    formato: Literal["csv", "json"] = Query("csv"),
):
    resultado = _resultado_listo(trabajo_id)
    df = tabla_dte(resultado, tabla)
    if formato == "json":
        return {"tabla": tabla, "columnas": list(df.columns), "filas": df.to_dict(orient="records")}
    if tabla == "serie_regional":
        df = df.astype(object).where(df.notna(), None)
        contenido = df.to_csv(index=False, lineterminator="\n", float_format="%.17g")
    else:
        contenido = df.to_csv(index=False, lineterminator="\n")
    region = resultado["metadata"].get("region") or {}
    nombre = f"dte_{region.get('id', trabajo_id)}_{tabla}.csv"
    return PlainTextResponse(contenido, media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{nombre}"'})
