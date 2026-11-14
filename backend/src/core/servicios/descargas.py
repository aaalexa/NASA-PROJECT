"""Gestor de tareas de descarga de NASA Earthdata en segundo plano para la API."""
from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from core.config import obtener_ajustes
from core.motor.datos import BBox, descargar_variable

EstadoTarea = Literal["pendiente", "ejecutando", "completada", "error"]


@dataclass
class TareaDescarga:
    id: str
    variable: str
    region: str
    bbox: BBox
    inicio: str
    fin: str
    estado: EstadoTarea = "pendiente"
    paso_actual: int = 0
    total_pasos: int = 0
    mensaje: str = "En cola"
    creada_en: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    actualizada_en: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resultado: dict[str, Any] | None = None
    error: str | None = None

    def a_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "variable": self.variable,
            "region": self.region,
            "bbox": list(self.bbox),
            "inicio": self.inicio,
            "fin": self.fin,
            "estado": self.estado,
            "paso_actual": self.paso_actual,
            "total_pasos": self.total_pasos,
            "mensaje": self.mensaje,
            "creada_en": self.creada_en,
            "actualizada_en": self.actualizada_en,
            "resultado": self.resultado,
            "error": self.error,
        }


class GestorDescargas:
    """Ejecuta descargas año a año de forma controlada y conserva el estado de cada tarea."""

    def __init__(self, max_trabajadores: int | None = None):
        n = max_trabajadores or obtener_ajustes().max_descargas
        self._pool = ThreadPoolExecutor(max_workers=n, thread_name_prefix="nasa-descarga")
        self._lock = threading.Lock()
        self._tareas: dict[str, TareaDescarga] = {}

    def _actualizar(self, tarea_id: str, **cambios: Any) -> None:
        with self._lock:
            t = self._tareas[tarea_id]
            for k, v in cambios.items():
                setattr(t, k, v)
            t.actualizada_en = datetime.now(timezone.utc).isoformat()

    def lanzar(
        self,
        variable: str,
        region: str,
        bbox: BBox,
        inicio: str,
        fin: str,
        catalogo: dict[str, dict],
        *,
        forzar: bool = False,
        sincrono: bool = False,
    ) -> TareaDescarga:
        entrada = catalogo[variable]
        var_real = entrada["origen"] if entrada["grupo"] == "calculada" else variable
        tarea_id = uuid.uuid4().hex[:12]
        tarea = TareaDescarga(
            id=tarea_id,
            variable=var_real,
            region=region,
            bbox=bbox,
            inicio=inicio,
            fin=fin,
        )
        with self._lock:
            self._tareas[tarea_id] = tarea

        def _ejecutar() -> None:
            self._actualizar(tarea_id, estado="ejecutando", mensaje="Iniciando descarga")

            def _progreso(actual: int, total: int, msg: str) -> None:
                self._actualizar(tarea_id, paso_actual=actual, total_pasos=total, mensaje=msg)

            try:
                res = descargar_variable(
                    var_real,
                    region,
                    bbox,
                    inicio,
                    fin,
                    catalogo,
                    progreso=_progreso,
                    forzar=forzar,
                )
                self._actualizar(
                    tarea_id,
                    estado="completada",
                    mensaje="Descarga completada",
                    resultado=res,
                )
            except Exception as exc:  # noqa: BLE001 — registramos el error en la tarea
                self._actualizar(tarea_id, estado="error", mensaje="Falló la descarga", error=str(exc))

        if sincrono:
            _ejecutar()
        else:
            self._pool.submit(_ejecutar)
        return self.obtener(tarea_id)

    def obtener(self, tarea_id: str) -> TareaDescarga:
        with self._lock:
            if tarea_id not in self._tareas:
                raise KeyError(f"No existe la tarea de descarga '{tarea_id}'")
            return self._tareas[tarea_id]

    def listar(self) -> list[dict[str, Any]]:
        with self._lock:
            return [t.a_dict() for t in reversed(list(self._tareas.values()))]


_GESTOR: GestorDescargas | None = None
_LOCK_GESTOR = threading.Lock()


def obtener_gestor_descargas() -> GestorDescargas:
    global _GESTOR
    with _LOCK_GESTOR:
        if _GESTOR is None:
            _GESTOR = GestorDescargas()
        return _GESTOR

