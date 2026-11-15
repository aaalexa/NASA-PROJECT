"""Trabajos en segundo plano para el análisis Down to Earth con datos reales de NASA.

Descargar 4 productos × 288 meses por OPeNDAP tarda minutos, más de lo que aguanta una petición HTTP. Un trabajo:
  1. descarga P, T, SM y ET de la región (progreso por variable),
  2. limpia y analiza (`analizar_region_real`),
  3. guarda el resultado en memoria RAM para que el frontend lo consulte.
Los cubos quedan además en la caché LRU, así que `GET /down-to-earth/analisis?estricto_memoria=true` para la misma
región y período responde al instante después.
"""
from __future__ import annotations

import logging
import threading
import uuid
from collections import OrderedDict
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from core.config import obtener_ajustes
from core.motor.down_to_earth import ORDEN_VARIABLES_DTE
from core.servicios.calculo_dte import analizar_region_real
from core.servicios.regiones import resolver_region

logger = logging.getLogger(__name__)

EstadoTrabajo = Literal["pendiente", "ejecutando", "completado", "error"]
MAX_TRABAJOS_GUARDADOS = 50
ETAPAS = (*ORDEN_VARIABLES_DTE, "analisis")


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TrabajoDTE:
    id: str
    region: str
    bbox: list[float]
    inicio: str
    fin: str
    alfa: float
    estado: EstadoTrabajo = "pendiente"
    etapa: str = "en cola"
    paso_actual: int = 0
    total_pasos: int = 0
    mensaje: str = "En cola"
    etapas_completadas: list[str] = field(default_factory=list)
    creado_en: str = field(default_factory=_ahora)
    actualizado_en: str = field(default_factory=_ahora)
    resultado: dict[str, Any] | None = None
    error: str | None = None

    @property
    def porcentaje(self) -> float:
        """Avance aproximado: cada variable pesa 24 % y el análisis el 4 % final."""
        if self.estado == "completado":
            return 100.0
        hechas = len([e for e in self.etapas_completadas if e in ORDEN_VARIABLES_DTE])
        parcial = (self.paso_actual / self.total_pasos) if self.total_pasos and self.etapa in ORDEN_VARIABLES_DTE else 0
        return round(min(99.0, 24.0 * (hechas + parcial) + (2.0 if self.etapa == "analisis" else 0.0)), 1)

    def a_dict(self) -> dict[str, Any]:
        base = f"/api/v1/down-to-earth/trabajos/{self.id}"
        return {
            "id": self.id,
            "region": self.region,
            "bbox": self.bbox,
            "inicio": self.inicio,
            "fin": self.fin,
            "alfa": self.alfa,
            "estado": self.estado,
            "etapa": self.etapa,
            "paso_actual": self.paso_actual,
            "total_pasos": self.total_pasos,
            "porcentaje": self.porcentaje,
            "mensaje": self.mensaje,
            "etapas": list(ETAPAS),
            "etapas_completadas": list(self.etapas_completadas),
            "creado_en": self.creado_en,
            "actualizado_en": self.actualizado_en,
            "error": self.error,
            "enlaces": {
                "estado": base,
                "resultado": f"{base}/resultado",
                "tablas": {t: f"{base}/tablas/{t}" for t in ("mensual", "anual", "limpieza", "diccionario",
                                                            "serie_regional")},
            },
        }


class GestorTrabajosDTE:
    """Ejecuta los trabajos en un pool limitado y conserva en RAM los últimos MAX_TRABAJOS_GUARDADOS."""

    def __init__(self, max_trabajadores: int | None = None):
        n = max_trabajadores or obtener_ajustes().max_descargas
        self._pool = ThreadPoolExecutor(max_workers=n, thread_name_prefix="nasa-dte")
        self._lock = threading.Lock()
        self._trabajos: OrderedDict[str, TrabajoDTE] = OrderedDict()
        self._precarga: list[str] = []

    def _actualizar(self, trabajo_id: str, **cambios: Any) -> None:
        with self._lock:
            t = self._trabajos[trabajo_id]
            for k, v in cambios.items():
                setattr(t, k, v)
            t.actualizado_en = _ahora()

    def lanzar(
        self,
        *,
        region: str | None,
        bbox: Sequence[float] | None,
        inicio: str,
        fin: str,
        alfa: float = 0.05,
        sincrono: bool = False,
        forzar: bool = False,
    ) -> TrabajoDTE:
        """Crea un trabajo, o devuelve el existente con los mismos parámetros (pendiente, ejecutando o completado).

        La deduplicación evita descargar dos veces lo mismo si el frontend reintenta o hay varias pestañas.
        `forzar=True` crea siempre uno nuevo.
        """
        reg = resolver_region(region, bbox)
        bbox_r = [float(v) for v in reg.bbox]
        with self._lock:
            if not forzar:
                for previo in reversed(list(self._trabajos.values())):
                    if (previo.region, previo.bbox, previo.inicio, previo.fin, previo.alfa) == (
                        reg.id, bbox_r, inicio, fin, alfa
                    ) and previo.estado in ("pendiente", "ejecutando", "completado"):
                        return previo
            trabajo = TrabajoDTE(id=uuid.uuid4().hex[:12], region=reg.id, bbox=bbox_r,
                                 inicio=inicio, fin=fin, alfa=alfa)
            self._trabajos[trabajo.id] = trabajo
            while len(self._trabajos) > MAX_TRABAJOS_GUARDADOS:
                self._trabajos.popitem(last=False)

        def _progreso(etapa: str, actual: int, total: int, msg: str) -> None:
            with self._lock:
                t = self._trabajos.get(trabajo.id)
                if t is None:
                    return
                if t.etapa != etapa and t.etapa in ETAPAS and t.etapa not in t.etapas_completadas:
                    t.etapas_completadas.append(t.etapa)
                t.etapa, t.paso_actual, t.total_pasos, t.mensaje = etapa, actual, total, msg
                t.actualizado_en = _ahora()

        def _ejecutar() -> None:
            self._actualizar(trabajo.id, estado="ejecutando", mensaje="Iniciando descarga OPeNDAP")
            try:
                res = analizar_region_real(
                    region=region, bbox=bbox, inicio=inicio, fin=fin, alfa=alfa, progreso=_progreso
                )
                self._actualizar(trabajo.id, estado="completado", etapa="completado", mensaje="Análisis completado",
                                 resultado=res, etapas_completadas=list(ETAPAS))
            except Exception as exc:  # noqa: BLE001 — el error queda en el trabajo
                self._actualizar(trabajo.id, estado="error", mensaje="Falló el trabajo",
                                 error=f"{type(exc).__name__}: {exc}")

        if sincrono:
            _ejecutar()
        else:
            self._pool.submit(_ejecutar)
        return self.obtener(trabajo.id)

    def precargar(self, regiones: Sequence[str], inicio: str, fin: str) -> list[TrabajoDTE]:
        """Lanza en segundo plano el análisis real de cada región (NASA_DTE_PRECARGA). Ignora ids desconocidos."""
        lanzados: list[TrabajoDTE] = []
        for r in regiones:
            try:
                lanzados.append(self.lanzar(region=r, bbox=None, inicio=inicio, fin=fin))
            except KeyError as exc:
                logger.warning("NASA_DTE_PRECARGA: región desconocida %r (%s)", r, exc)
        with self._lock:
            self._precarga = [t.id for t in lanzados]
        return lanzados

    def estado_precarga(self) -> list[dict[str, Any]]:
        with self._lock:
            ids = list(self._precarga)
            return [
                {"id": t.id, "region": t.region, "estado": t.estado, "porcentaje": t.porcentaje, "error": t.error}
                for i in ids if (t := self._trabajos.get(i)) is not None
            ]

    def obtener(self, trabajo_id: str) -> TrabajoDTE:
        with self._lock:
            if trabajo_id not in self._trabajos:
                raise KeyError(f"No existe el trabajo Down to Earth '{trabajo_id}'")
            return self._trabajos[trabajo_id]

    def listar(self) -> list[dict[str, Any]]:
        with self._lock:
            return [t.a_dict() for t in reversed(list(self._trabajos.values()))]


_GESTOR: GestorTrabajosDTE | None = None
_LOCK_GESTOR = threading.Lock()


def obtener_gestor_trabajos_dte() -> GestorTrabajosDTE:
    global _GESTOR
    with _LOCK_GESTOR:
        if _GESTOR is None:
            _GESTOR = GestorTrabajosDTE()
        return _GESTOR
