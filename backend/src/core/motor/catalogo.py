"""Catálogo de variables: carga, validación y conversión de unidades (skill catalogo-variables).

catalogo.yaml es la única descripción de cada variable. Este módulo lo valida juntando TODOS los errores en un
solo ValueError y aplica las conversiones de una lista blanca (sin eval). Ninguna otra parte del código convierte
unidades crudas de NASA.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import xarray as xr
import yaml

UNIDADES_CONOCIDAS: frozenset[str] = frozenset({
    "mm/dia", "mm/mes", "mm/anio", "mm/h", "mm",
    "kg m-2 s-1", "kg m-2", "kg m-2 3h-1",
    "K", "degC",
    "1", "escalado", "clase IGBP", "booleano", "fraccion",
    "personas", "dias",
})
GRUPOS: frozenset[str] = frozenset({"lluvia", "causa", "agua", "social", "calculada"})
FRECUENCIAS: frozenset[str] = frozenset({"diaria", "mensual", "anual"})
OPERACIONES: frozenset[str] = frozenset({"ninguna", "factor", "suma", "dias_del_mes", "clases"})
AGREGACIONES: frozenset[str] = frozenset({"suma", "media"})
METODOS_DESCARGA: frozenset[str] = frozenset({"opendap", "remoto", "descarga"})
INDICADORES: frozenset[str] = frozenset({"cdd", "r20mm", "dias_humedos", "prcptot", "sdii"})

OBLIGATORIOS: tuple[str, ...] = (
    "id", "grupo", "nombre_simple", "definicion_simple", "dataset", "short_name", "variable",
    "unidad_original", "conversion", "unidad_final", "desde", "resolucion", "frecuencia",
)
OBLIGATORIOS_DATASET: tuple[str, ...] = ("id", "nombre", "descripcion", "short_names", "desde", "resolucion")

_RE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_RE_DESDE = re.compile(r"^\d{4}(-(0[1-9]|1[0-2]))?$")


def _es_numero(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def validar_entrada(entrada: dict) -> list[str]:
    """Valida una variable aislada. Devuelve la lista de errores ([] = válida), cada uno prefijado con el id."""
    if not isinstance(entrada, dict):
        return [f"entrada no es un diccionario: {entrada!r}"]
    vid = entrada.get("id", "<sin id>")
    errores: list[str] = []

    def err(msg: str) -> None:
        errores.append(f"{vid}: {msg}")

    for campo in OBLIGATORIOS:
        if campo not in entrada:
            err(f"falta '{campo}'")
    if "id" in entrada and not (isinstance(vid, str) and _RE_ID.match(vid)):
        err("'id' debe ser snake_case en minúsculas")
    grupo = entrada.get("grupo")
    if grupo is not None and grupo not in GRUPOS:
        err(f"grupo '{grupo}' desconocido (válidos: {sorted(GRUPOS)})")
    frecuencia = entrada.get("frecuencia")
    if frecuencia is not None and frecuencia not in FRECUENCIAS:
        err(f"frecuencia '{frecuencia}' desconocida (válidas: {sorted(FRECUENCIAS)})")
    for campo in ("unidad_original", "unidad_final"):
        u = entrada.get(campo)
        if u is not None and u not in UNIDADES_CONOCIDAS:
            err(f"unidad '{u}' desconocida en '{campo}'")
    if "desde" in entrada and not _RE_DESDE.match(str(entrada["desde"])):
        err(f"'desde' debe ser AAAA-MM o AAAA, no {entrada['desde']!r}")
    if "short_name" in entrada and entrada["short_name"] is None and grupo != "calculada":
        err("'short_name' solo puede ser null en el grupo 'calculada'")

    conv = entrada.get("conversion")
    if "conversion" in entrada:
        if not isinstance(conv, dict) or "op" not in conv:
            err("'conversion' debe ser un dict con 'op'")
        elif conv["op"] not in OPERACIONES:
            err(f"op '{conv['op']}' desconocida (válidas: {sorted(OPERACIONES)})")
        elif conv["op"] in ("factor", "suma") and not _es_numero(conv.get("valor")):
            err(f"op '{conv['op']}' necesita 'valor' numérico")
        elif conv["op"] == "clases":
            valores = conv.get("valores")
            if not (isinstance(valores, list) and valores and all(isinstance(v, int) for v in valores)):
                err("op 'clases' necesita 'valores' como lista de enteros")

    # Campos opcionales del proyecto.
    rango = entrada.get("rango_valido")
    if rango is not None:
        if not (isinstance(rango, list) and len(rango) == 2
                and all(v is None or _es_numero(v) for v in rango)):
            err("'rango_valido' debe ser [min, max] (números o null)")
        elif rango[0] is not None and rango[1] is not None and rango[0] >= rango[1]:
            err("'rango_valido' necesita min < max")
    agg = entrada.get("agregacion_anual")
    if agg is not None and agg not in AGREGACIONES:
        err(f"agregacion_anual '{agg}' desconocida (válidas: {sorted(AGREGACIONES)})")
    if agg == "suma" and frecuencia != "anual" and entrada.get("unidad_final") not in ("mm/mes", "mm/dia", "mm/anio"):
        err("agregacion_anual 'suma' solo es válida para cantidades de lluvia (mm/mes o mm/dia)")
    metodo = entrada.get("metodo_descarga")
    if metodo is not None and metodo not in METODOS_DESCARGA:
        err(f"metodo_descarga '{metodo}' desconocido (válidos: {sorted(METODOS_DESCARGA)})")
    if grupo == "calculada":
        if not entrada.get("origen"):
            err("las variables 'calculada' necesitan 'origen'")
        ind = str(entrada.get("indicador", "")).lower()
        if ind not in INDICADORES:
            err(f"indicador '{entrada.get('indicador')}' desconocido (válidos: {sorted(INDICADORES)})")
    return errores


def _validar_dataset(ds: dict) -> list[str]:
    did = ds.get("id", "<sin id>") if isinstance(ds, dict) else "<?>"
    if not isinstance(ds, dict):
        return [f"dataset no es un diccionario: {ds!r}"]
    errores = [f"dataset {did}: falta '{c}'" for c in OBLIGATORIOS_DATASET if c not in ds]
    if "short_names" in ds and not (isinstance(ds["short_names"], list) and ds["short_names"]):
        errores.append(f"dataset {did}: 'short_names' debe ser una lista no vacía")
    return errores


def _leer_yaml(ruta: str | Path) -> dict:
    with open(ruta, encoding="utf-8") as f:
        datos = yaml.safe_load(f) or {}
    if not isinstance(datos, dict):
        raise ValueError(f"{ruta}: el YAML debe ser un diccionario con la clave 'variables'")
    return datos


def cargar_catalogo(ruta: str | Path) -> dict[str, dict]:
    """Carga y valida catalogo.yaml. Devuelve {id: entrada}. Lanza un ValueError que enumera TODOS los errores."""
    datos = _leer_yaml(ruta)
    variables = datos.get("variables")
    if not isinstance(variables, list):
        raise ValueError(f"{ruta}: falta la lista 'variables'")
    datasets = datos.get("datasets") or []
    ids_dataset = {d.get("id") for d in datasets if isinstance(d, dict)}

    errores: list[str] = []
    for d in datasets:
        errores += _validar_dataset(d)
    catalogo: dict[str, dict] = {}
    for entrada in variables:
        errores += validar_entrada(entrada)
        if not isinstance(entrada, dict) or "id" not in entrada:
            continue
        vid = entrada["id"]
        if vid in catalogo:
            errores.append(f"{vid}: id repetido")
            continue
        fuente = entrada.get("fuente")
        if datasets and fuente is not None and fuente not in ids_dataset:
            errores.append(f"{vid}: fuente '{fuente}' no está en 'datasets'")
        catalogo[vid] = entrada
    for vid, entrada in catalogo.items():
        origen = entrada.get("origen")
        if origen is not None and origen not in catalogo:
            errores.append(f"{vid}: origen '{origen}' no existe en el catálogo")
    if errores:
        raise ValueError("catálogo inválido: " + "; ".join(errores))
    return catalogo


def cargar_datasets(ruta: str | Path) -> dict[str, dict]:
    """Devuelve {id: dataset} de la sección 'datasets' (validada)."""
    datasets = _leer_yaml(ruta).get("datasets") or []
    errores = [e for d in datasets for e in _validar_dataset(d)]
    if errores:
        raise ValueError("catálogo inválido: " + "; ".join(errores))
    return {d["id"]: d for d in datasets}


def variables_por_grupo(catalogo: dict[str, dict], grupo: str) -> list[str]:
    """Ids de las variables de un grupo, en el orden del catálogo."""
    if grupo not in GRUPOS:
        raise ValueError(f"grupo '{grupo}' desconocido (válidos: {sorted(GRUPOS)})")
    return [vid for vid, e in catalogo.items() if e["grupo"] == grupo]


def aplicar_rango_valido(da: xr.DataArray, entrada: dict) -> xr.DataArray:
    """Pone NaN fuera de entrada['rango_valido'] (en unidades ORIGINALES). Sin rango, devuelve da sin cambios."""
    rango = entrada.get("rango_valido")
    if not rango:
        return da
    lo, hi = rango
    ok = da.notnull()
    if lo is not None:
        ok = ok & (da >= lo)
    if hi is not None:
        ok = ok & (da <= hi)
    out = da.where(ok)
    out.attrs = dict(da.attrs)
    return out


def convertir(da: xr.DataArray, entrada: dict) -> xr.DataArray:
    """Aplica entrada['conversion'] y deja attrs['units'] = unidad_final. No modifica la entrada.

    La unidad que traía el archivo se guarda en attrs['units_archivo'] (no se compara: NASA la escribe de
    muchas formas). 'dias_del_mes' necesita una coordenada 'time' datetime64.
    """
    conv = entrada["conversion"]
    op = conv["op"]
    if op == "ninguna":
        out = da.copy()
    elif op == "factor":
        out = da * float(conv["valor"])
    elif op == "suma":
        out = da + float(conv["valor"])
    elif op == "dias_del_mes":
        if "time" not in da.coords:
            raise ValueError(f"{entrada['id']}: 'dias_del_mes' necesita una coordenada 'time'")
        out = da * da["time"].dt.days_in_month
    elif op == "clases":
        out = xr.where(da.isin(conv["valores"]), 1.0, 0.0).where(da.notnull())
    else:
        raise ValueError(f"{entrada.get('id')}: op '{op}' desconocida")
    attrs = {k: v for k, v in da.attrs.items() if k not in ("units", "_FillValue", "missing_value")}
    if "units" in da.attrs:
        attrs["units_archivo"] = str(da.attrs["units"])
    attrs["units"] = entrada["unidad_final"]
    out.attrs = attrs
    out.name = da.name
    return out


def cambiar_unidad(da: xr.DataArray, destino: str) -> xr.DataArray:
    """Pasa una serie/cubo MENSUAL de lluvia entre mm/dia y mm/mes (× o ÷ días reales del mes).

    Sirve para comparar fuentes en la misma unidad (GPCP llega en mm/mes; MERRA-2 e IMERG en mm/dia).
    """
    origen = da.attrs.get("units")
    if origen == destino:
        return da
    if {origen, destino} != {"mm/dia", "mm/mes"}:
        raise ValueError(f"no sé convertir '{origen}' a '{destino}' (solo mm/dia ↔ mm/mes)")
    if "time" not in da.coords:
        raise ValueError("cambiar_unidad necesita una serie mensual con coordenada 'time'")
    dias = da["time"].dt.days_in_month
    out = da * dias if destino == "mm/mes" else da / dias
    out.attrs = {**da.attrs, "units": destino}
    out.name = da.name
    return out

