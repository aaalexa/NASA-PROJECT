"""Motor de cálculo de "Las dos caras de la lluvia" (GPCP, MERRA-2 y GPM IMERG)."""
from __future__ import annotations

from core.motor import catalogo, datos, escaner, indicadores, series, tendencias

__all__ = [
    "catalogo",
    "datos",
    "escaner",
    "indicadores",
    "series",
    "tendencias",
]
