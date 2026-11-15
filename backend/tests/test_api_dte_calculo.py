"""Endpoints de cálculo Down to Earth: /calcular (JSON y CSV) y /trabajos (datos reales simulados sin red).

La exactitud se comprueba contra el script de referencia de la skill con los CSV SIMULADOS de evals/files.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from core.api.app import crear_app
from core.motor.datos import DatosNoDisponibles
from core.servicios import calculo_dte, consultas
from core.servicios.regiones import resolver_region

SKILL = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "analisis-down-to-earth"
FILES = SKILL / "evals" / "files"


@pytest.fixture()
def cliente(dir_datos_temporal, monkeypatch):
    from core.servicios import trabajos_dte

    monkeypatch.setattr(trabajos_dte, "_GESTOR", None)  # gestor limpio por test (la deduplicación es por proceso)
    return TestClient(crear_app())


def _referencia_skill(archivo: str, unidades: str) -> dict:
    spec = importlib.util.spec_from_file_location("analisis_dte_skill_api", SKILL / "scripts" / "analisis_dte.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    filas, campos = mod.leer_csv(str(FILES / archivo))
    return mod.analizar(filas, campos, unidades=unidades, simulado=True, usar_statsmodels=True)


def _comparar_con_skill(res: dict, ref: dict) -> None:
    ref_vars = {v["id"]: v for v in ref["variables"]}
    for c in ("P", "T", "SM", "ET"):
        b, s = res["variables"][c], ref_vars[c]
        assert b["slope_decade"] == pytest.approx(s["slope_decade"], rel=1e-9)
        assert b["ci95"][0] == pytest.approx(s["ci95"][0], rel=1e-9)
        assert b["p_holm"] == pytest.approx(s["p_holm"], rel=1e-9, abs=1e-300)
        assert b["label"] == s["label"]
    ref_pares = {p["par"].replace("–", "-"): p for p in ref["joint"]["pairs"]}
    for par, info in res["joint"]["pairs"].items():
        assert info["r"] == pytest.approx(ref_pares[par]["r"], abs=1e-12)
        assert info["n"] == ref_pares[par]["n"]


@pytest.mark.skipif(not FILES.exists(), reason="skill no disponible")
def test_calcular_json_unidades_finales_igual_al_script(cliente):
    df = pd.read_csv(FILES / "dte_simulado_completo.csv", dtype={"fecha": str})
    serie = json.loads(df.to_json(orient="records"))
    r = cliente.post("/api/v1/down-to-earth/calcular",
                     json={"serie": serie, "simulado": True, "incluir_tablas": True})
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["metadata"]["simulated"] is True
    assert res["metadata"]["trend_span"]["start"] == 2001 and res["metadata"]["trend_span"]["end"] == 2024
    assert set(res["tablas"]) == {"mensual", "anual", "diccionario"}
    assert len(res["tablas"]["mensual"]) == 288 and len(res["tablas"]["anual"]) == 24
    _comparar_con_skill(res, _referencia_skill("dte_simulado_completo.csv", "finales"))


@pytest.mark.skipif(not FILES.exists(), reason="skill no disponible")
def test_calcular_csv_unidades_originales_con_huecos_igual_al_script(cliente):
    with open(FILES / "dte_simulado_originales.csv", "rb") as f:
        r = cliente.post(
            "/api/v1/down-to-earth/calcular/csv",
            files={"archivo": ("dte_simulado_originales.csv", f, "text/csv")},
            data={"unidades": "originales", "simulado": "true"},
        )
    assert r.status_code == 200, r.text
    res = r.json()
    tr = res["metadata"]["trend_span"]
    assert (tr["start"], tr["end"], tr["n_years"]) == (2002, 2012, 11)
    assert res["metadata"]["input"]["columns_used"] == {
        "P": "sat_gauge_precip", "T": "T2M", "SM": "SoilMoi0_10cm_inst", "ET": "Evap_tavg"}
    log = res["data_cleaning"]["log"]
    assert any(e["fecha"] == "2001-03" and e["variable"] == "T" and "relleno" in e["motivo"] for e in log)
    assert any(e["fecha"] == "2013-06" and "mes ausente" in e["motivo"] for e in log)
    assert res["variables"]["T"]["monthly"][2]["value"] is None  # 2001-03 nunca se rellena
    _comparar_con_skill(res, _referencia_skill("dte_simulado_originales.csv", "originales"))


def test_calcular_valida_entrada(cliente):
    r = cliente.post("/api/v1/down-to-earth/calcular", json={"serie": [{"fecha": "2001-01"}], "unidades": "kelvin"})
    assert r.status_code == 422
    r2 = cliente.post("/api/v1/down-to-earth/calcular/csv",
                      files={"archivo": ("x.csv", b"col_a,col_b\n1,2\n", "text/csv")})
    assert r2.status_code == 400 and r2.json()["error"] == "parametro_invalido"
    # Una sola variable: las otras se publican como no evaluables, sin inventar datos
    serie = [{"fecha": f"{a}-{m:02d}", "P": 50.0 + a - 2001 + (m % 3)} for a in range(2001, 2025) for m in range(1, 13)]
    r3 = cliente.post("/api/v1/down-to-earth/calcular", json={"serie": serie})
    assert r3.status_code == 200
    res = r3.json()
    assert res["variables"]["P"]["slope_decade"] is not None
    assert res["variables"]["T"]["label"].startswith("no evaluable")
    assert res["variables"]["T"]["p_holm"] is None
    assert res["metadata"]["simulated"] is False


def _cubo_falso(variable, region, bbox, inicio, fin, catalogo, descargar=False):
    reg = resolver_region(region, None)
    return consultas._cubo_sintetico(variable, catalogo[variable], reg, inicio, fin)


def test_trabajo_region_real_ciclo_completo(cliente, monkeypatch):
    monkeypatch.setattr(calculo_dte, "descargar_variable",
                        lambda vid, reg_id, bbox, ini, fin, cat, progreso=None: progreso and progreso(288, 288, "ok"))
    monkeypatch.setattr(consultas, "obtener_variable", _cubo_falso)

    r = cliente.post("/api/v1/down-to-earth/trabajos", json={"region": "sahel", "sincrono": True})
    assert r.status_code == 202, r.text
    t = r.json()
    assert t["estado"] == "completado" and t["porcentaje"] == 100.0
    assert t["etapas_completadas"] == ["P", "T", "SM", "ET", "analisis"]

    estado = cliente.get(f"/api/v1/down-to-earth/trabajos/{t['id']}").json()
    assert estado["estado"] == "completado"
    assert any(x["id"] == t["id"] for x in cliente.get("/api/v1/down-to-earth/trabajos").json()["trabajos"])

    res = cliente.get(f"/api/v1/down-to-earth/trabajos/{t['id']}/resultado").json()
    assert res["metadata"]["source"] == "opendap_memoria" and res["metadata"]["simulated"] is False
    assert set(res["variables"]) == {"P", "T", "SM", "ET"}

    csv_m = cliente.get(f"/api/v1/down-to-earth/trabajos/{t['id']}/tablas/mensual")
    assert csv_m.status_code == 200 and csv_m.headers["content-type"].startswith("text/csv")
    assert csv_m.text.splitlines()[0].startswith("fecha,anio,mes,dias_mes,P_mm_mes,T_C,SM_m3_m3,ET_mm_mes")
    js = cliente.get(f"/api/v1/down-to-earth/trabajos/{t['id']}/tablas/anual", params={"formato": "json"}).json()
    assert js["tabla"] == "anual" and len(js["filas"]) == 24
    serie = cliente.get(f"/api/v1/down-to-earth/trabajos/{t['id']}/tablas/serie_regional").text.splitlines()
    assert serie[0] == "fecha,P,T,SM,ET" and len(serie) == 289


def test_trabajo_con_error_no_usa_sinteticos_y_resultado_da_409(cliente, monkeypatch):
    monkeypatch.setattr(calculo_dte, "descargar_variable", lambda *a, **k: None)

    def _falla(variable, region, bbox, inicio, fin, catalogo, descargar=False):
        raise DatosNoDisponibles(variable, region, inicio, fin)

    monkeypatch.setattr(consultas, "obtener_variable", _falla)
    t = cliente.post("/api/v1/down-to-earth/trabajos", json={"region": "sahel", "sincrono": True}).json()
    assert t["estado"] == "error" and "DatosNoDisponibles" in t["error"]
    r = cliente.get(f"/api/v1/down-to-earth/trabajos/{t['id']}/resultado")
    assert r.status_code == 409
    assert cliente.get("/api/v1/down-to-earth/trabajos/noexiste").status_code == 404


def test_analisis_get_respeta_el_modelo_de_respuesta(cliente):
    r = cliente.get("/api/v1/down-to-earth/analisis", params={"region": "sahel", "sintetico": True})
    assert r.status_code == 200
    res = r.json()
    assert res["metadata"]["simulated"] is True
    assert "data_cleaning" in res and "trend_span" in res["metadata"]
    for c in ("P", "T", "SM", "ET"):
        assert "sin cambio" not in res["variables"][c]["label"].lower()


def test_trabajos_se_deduplican_salvo_forzar(cliente, monkeypatch):
    monkeypatch.setattr(calculo_dte, "descargar_variable", lambda *a, **k: None)
    monkeypatch.setattr(consultas, "obtener_variable", _cubo_falso)
    cuerpo = {"region": "sahel", "inicio": "2001-01", "fin": "2024-12", "sincrono": True}
    t1 = cliente.post("/api/v1/down-to-earth/trabajos", json=cuerpo).json()
    t2 = cliente.post("/api/v1/down-to-earth/trabajos", json=cuerpo).json()
    assert t1["id"] == t2["id"]
    t3 = cliente.post("/api/v1/down-to-earth/trabajos", json={**cuerpo, "forzar": True}).json()
    assert t3["id"] != t1["id"]
    t4 = cliente.post("/api/v1/down-to-earth/trabajos", json={**cuerpo, "fin": "2023-12"}).json()
    assert t4["id"] not in (t1["id"], t3["id"])


def test_precarga_al_arrancar_solo_con_credenciales(monkeypatch, dir_datos_temporal):
    import importlib

    from core.config import obtener_ajustes

    modulo_app = importlib.import_module("core.api.app")
    from core.servicios.trabajos_dte import GestorTrabajosDTE

    gestor = GestorTrabajosDTE(max_trabajadores=1)
    llamadas: list[tuple] = []
    monkeypatch.setattr(gestor, "lanzar", lambda **kw: llamadas.append((kw["region"], kw["inicio"], kw["fin"]))
                        or type("T", (), {"id": kw["region"]})())
    monkeypatch.setattr(modulo_app, "obtener_gestor_trabajos_dte", lambda: gestor)
    monkeypatch.setenv("NASA_DTE_PRECARGA", "sahel, corredor_seco_centroamericano")
    obtener_ajustes.cache_clear()
    try:
        monkeypatch.setattr(modulo_app, "_credenciales_configuradas", lambda: {"listo": False})
        with TestClient(modulo_app.crear_app()):
            pass
        assert llamadas == []
        monkeypatch.setattr(modulo_app, "_credenciales_configuradas", lambda: {"listo": True})
        with TestClient(modulo_app.crear_app()) as c:
            assert c.get("/api/v1/salud").status_code == 200
        assert llamadas == [("sahel", "2001-01", "2024-12"), ("corredor_seco_centroamericano", "2001-01", "2024-12")]
    finally:
        monkeypatch.delenv("NASA_DTE_PRECARGA")
        obtener_ajustes.cache_clear()
