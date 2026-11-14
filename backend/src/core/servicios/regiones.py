"""Catálogo de regiones predefinidas y resolución de bounding boxes para la API."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

import yaml

from core.config import obtener_ajustes
from core.motor.datos import BBox, slug_bbox, slug_region, validar_bbox


@dataclass(frozen=True)
class RegionResuelta:
    id: str
    nombre: str
    descripcion: str
    bbox: BBox
    predefinida: bool

    def a_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "bbox": list(self.bbox),
            "predefinida": self.predefinida,
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
        )
    return regiones


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
            )
        rid = slug_bbox(bbox_val)
        return RegionResuelta(
            id=rid,
            nombre=f"Caja [{bbox_val[0]:g}, {bbox_val[1]:g}, {bbox_val[2]:g}, {bbox_val[3]:g}]",
            descripcion="Región definida por coordenadas bounding box",
            bbox=bbox_val,
            predefinida=False,
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

