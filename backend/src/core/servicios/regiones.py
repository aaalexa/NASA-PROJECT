"""Catálogo de regiones predefinidas y resolución de coordenadas reales y mallas NASA para la API."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import yaml

from core.config import obtener_ajustes
from core.motor.datos import BBox, slug_bbox, slug_region, validar_bbox

ZONAS_LATINOAMERICA: frozenset[str] = frozenset({"mexico", "centroamerica", "caribe", "sudamerica"})

# Especificaciones reales de los centros de celda de cada colección de NASA
_GRILLAS_COLECCIONES: dict[str, dict[str, float | str]] = {
    "gpcp": {
        "resolucion": "0.5° × 0.5°",
        "lat_min": -89.75,
        "lat_max": 89.75,
        "dlat": 0.5,
        "lon_min": -179.75,
        "lon_max": 179.75,
        "dlon": 0.5,
    },
    "merra2": {
        "resolucion": "0.5° × 0.625°",
        "lat_min": -90.0,
        "lat_max": 90.0,
        "dlat": 0.5,
        "lon_min": -180.0,
        "lon_max": 179.375,
        "dlon": 0.625,
    },
    "gldas": {
        "resolucion": "0.25° × 0.25°",
        "lat_min": -59.875,
        "lat_max": 89.875,
        "dlat": 0.25,
        "lon_min": -179.875,
        "lon_max": 179.875,
        "dlon": 0.25,
    },
    "imerg": {
        "resolucion": "0.1° × 0.1°",
        "lat_min": -89.95,
        "lat_max": 89.95,
        "dlat": 0.1,
        "lon_min": -179.95,
        "lon_max": 179.95,
        "dlon": 0.1,
    },
}


def calcular_coordenadas_bbox(bbox: BBox) -> dict[str, Any]:
    """Calcula la posición real de latitud/longitud (límites, centro, esquinas y GeoJSON) a partir del bbox."""
    oeste, sur, este, norte = (float(v) for v in bbox)
    centro_lat = round((sur + norte) / 2.0, 4)
    if oeste <= este:
        centro_lon = round((oeste + este) / 2.0, 4)
        ancho_lon = round(este - oeste, 4)
    else:
        centro_lon = round((((oeste + este + 360.0) / 2.0 + 180.0) % 360.0) - 180.0, 4)
        ancho_lon = round((180.0 - oeste) + (este + 180.0), 4)
    alto_lat = round(norte - sur, 4)

    return {
        "oeste": oeste,
        "sur": sur,
        "este": este,
        "norte": norte,
        "lon_min": oeste,
        "lat_min": sur,
        "lon_max": este,
        "lat_max": norte,
        "centro": {
            "lat": centro_lat,
            "lon": centro_lon,
        },
        "extension_grados": {
            "ancho_lon": ancho_lon,
            "alto_lat": alto_lat,
        },
        "esquinas": {
            "suroeste": {"lat": sur, "lon": oeste},
            "sureste": {"lat": sur, "lon": este},
            "noreste": {"lat": norte, "lon": este},
            "noroeste": {"lat": norte, "lon": oeste},
        },
        "poligono_geojson": {
            "type": "Polygon",
            "coordinates": [[
                [oeste, sur],
                [este, sur],
                [este, norte],
                [oeste, norte],
                [oeste, sur],
            ]],
        },
    }


def calcular_mallas_reales_bbox(bbox: BBox) -> dict[str, dict[str, Any]]:
    """Calcula los centros de celda reales de cada colección NASA (GPCP, MERRA-2, GLDAS, IMERG) dentro del bbox."""
    oeste, sur, este, norte = (float(v) for v in bbox)
    salida: dict[str, dict[str, Any]] = {}

    for nombre_col, g in _GRILLAS_COLECCIONES.items():
        lat_min_g = float(g["lat_min"])
        lat_max_g = float(g["lat_max"])
        dlat = float(g["dlat"])
        lon_min_g = float(g["lon_min"])
        lon_max_g = float(g["lon_max"])
        dlon = float(g["dlon"])

        n_lat_g = int(round((lat_max_g - lat_min_g) / dlat)) + 1
        n_lon_g = int(round((lon_max_g - lon_min_g) / dlon)) + 1
        lats = np.linspace(lat_min_g, lat_max_g, n_lat_g)
        lons = np.linspace(lon_min_g, lon_max_g, n_lon_g)

        sub_lats = lats[(lats >= sur) & (lats <= norte)]
        if sub_lats.size == 0:
            idx_c = int(np.abs(lats - (sur + norte) / 2.0).argmin())
            sub_lats = lats[idx_c : idx_c + 1]

        if oeste <= este:
            sub_lons = lons[(lons >= oeste) & (lons <= este)]
        else:
            sub_lons = lons[(lons >= oeste) | (lons <= este)]
        if sub_lons.size == 0:
            clon = (oeste + este) / 2.0 if oeste <= este else ((oeste + este + 360.0) / 2.0 + 180.0) % 360.0 - 180.0
            idx_l = int(np.abs(lons - clon).argmin())
            sub_lons = lons[idx_l : idx_l + 1]

        n_lat = int(sub_lats.size)
        n_lon = int(sub_lons.size)
        salida[nombre_col] = {
            "resolucion": str(g["resolucion"]),
            "lat_min_real": round(float(sub_lats.min()), 4),
            "lat_max_real": round(float(sub_lats.max()), 4),
            "lon_min_real": round(float(sub_lons.min()), 4),
            "lon_max_real": round(float(sub_lons.max()), 4),
            "n_lat": n_lat,
            "n_lon": n_lon,
            "n_celdas": n_lat * n_lon,
        }

    return salida


@dataclass(frozen=True)
class RegionResuelta:
    id: str
    nombre: str
    descripcion: str
    bbox: BBox
    predefinida: bool
    zona: str = "personalizada"
    pais: str = ""

    def a_dict(self) -> dict[str, Any]:
        oeste, sur, este, norte = (float(v) for v in self.bbox)
        coordenadas = calcular_coordenadas_bbox(self.bbox)
        return {
            "id": self.id,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "zona": self.zona,
            "pais": self.pais,
            "es_latinoamerica": self.zona in ZONAS_LATINOAMERICA,
            "bbox": [oeste, sur, este, norte],
            "predefinida": self.predefinida,
            "coordenadas": coordenadas,
            "mallas_reales": calcular_mallas_reales_bbox(self.bbox),
            "shortcut": {
                "region": self.id,
                "oeste": oeste,
                "sur": sur,
                "este": este,
                "norte": norte,
                "centro_lat": coordenadas["centro"]["lat"],
                "centro_lon": coordenadas["centro"]["lon"],
                "query_region": f"?region={self.id}",
                "query_bbox": f"?oeste={oeste:g}&sur={sur:g}&este={este:g}&norte={norte:g}",
            },
        }


@lru_cache(maxsize=4)
def cargar_regiones(ruta: str | Path | None = None) -> dict[str, RegionResuelta]:
    """Lee regiones.yaml y devuelve {id: RegionResuelta}."""
    ruta_real = Path(ruta) if ruta is not None else obtener_ajustes().ruta_regiones
    with open(ruta_real, encoding="utf-8") as f:
        datos = yaml.safe_load(f) or {}
    lista = datos.get("regiones") or []
    regiones: dict[str, RegionResuelta] = {}
    for r in lista:
        rid = slug_region(str(r["id"]))
        bbox = validar_bbox(r["bbox"])
        regiones[rid] = RegionResuelta(
            id=rid,
            nombre=str(r.get("nombre", rid)),
            descripcion=str(r.get("descripcion", "")),
            bbox=bbox,
            predefinida=True,
            zona=str(r.get("zona", "referencia_global")),
            pais=str(r.get("pais", "")),
        )
    return regiones


def listar_regiones_filtradas(
    *,
    zona: str | None = None,
    solo_latinoamerica: bool = False,
    ruta_regiones: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Devuelve la lista de regiones enriquecidas con sus coordenadas reales, filtrando opcionalmente por zona."""
    todas = [r.a_dict() for r in cargar_regiones(ruta_regiones).values()]
    if solo_latinoamerica:
        todas = [r for r in todas if r["es_latinoamerica"]]
    if zona:
        z_norm = zona.strip().lower()
        if z_norm in ("latinoamerica", "latam"):
            todas = [r for r in todas if r["es_latinoamerica"]]
        elif z_norm in ("mexico_centroamerica", "mesoamerica"):
            todas = [r for r in todas if r["zona"] in ("mexico", "centroamerica")]
        else:
            todas = [r for r in todas if r["zona"] == z_norm]
    return todas


def resolver_region(
    region: str | None = None,
    bbox: Sequence[float] | None = None,
    *,
    ruta_regiones: str | Path | None = None,
) -> RegionResuelta:
    """Resuelve una región por su id predefinido o por un bbox explícito [oeste, sur, este, norte].

    - Si se pasa `region` de regiones.yaml y no `bbox`, usa el bbox predefinido.
    - Si se pasa `bbox` (con o sin nombre `region`), valida el bbox y usa `region` como slug (o genera uno).
    """
    catalogo_reg = cargar_regiones(ruta_regiones)
    if bbox is not None:
        bbox_val = validar_bbox(bbox)
        if region:
            rid = slug_region(region)
            if rid in catalogo_reg and catalogo_reg[rid].bbox == bbox_val:
                return catalogo_reg[rid]
            return RegionResuelta(
                id=rid,
                nombre=region.strip(),
                descripcion=f"Región personalizada ({bbox_val[0]}, {bbox_val[1]}, {bbox_val[2]}, {bbox_val[3]})",
                bbox=bbox_val,
                predefinida=False,
                zona="personalizada",
            )
        rid = slug_bbox(bbox_val)
        return RegionResuelta(
            id=rid,
            nombre=f"Caja [{bbox_val[0]:g}, {bbox_val[1]:g}, {bbox_val[2]:g}, {bbox_val[3]:g}]",
            descripcion="Región definida por coordenadas bounding box",
            bbox=bbox_val,
            predefinida=False,
            zona="personalizada",
        )

    if not region:
        raise ValueError("Debes indicar 'region' (id predefinido) o 'bbox' ([oeste, sur, este, norte]).")
    rid = slug_region(region)
    if rid not in catalogo_reg:
        disponibles = ", ".join(sorted(catalogo_reg))
        raise KeyError(
            f"La región '{region}' no está en el catálogo de regiones predefinidas ({disponibles}). "
            "Pasa el parámetro 'bbox' (oeste, sur, este, norte) para consultar una región personalizada."
        )
    return catalogo_reg[rid]
