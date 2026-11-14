"""Alias de compatibilidad: redirige `import motor.*` a `core.motor.*` para los tests y scripts."""
from __future__ import annotations

import sys

import core.motor as _core_motor
from core.motor import catalogo, datos, escaner, indicadores, series, tendencias

for _nombre, _mod in (
    ("catalogo", catalogo),
    ("datos", datos),
    ("escaner", escaner),
    ("indicadores", indicadores),
    ("series", series),
    ("tendencias", tendencias),
):
    sys.modules[f"{__name__}.{_nombre}"] = _mod

__all__ = list(_core_motor.__all__)

