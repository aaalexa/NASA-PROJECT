"""Motor de cálculo de "Las dos caras de la lluvia" y "Down to Earth" (GPCP, MERRA-2, GLDAS y GPM IMERG)."""
from __future__ import annotations

from core.motor import catalogo, datos, down_to_earth, escaner, indicadores, series, tendencias

__all__ = [
    "catalogo",
    "datos",
    "down_to_earth",
    "escaner",
    "indicadores",
    "series",
    "tendencias",
]
