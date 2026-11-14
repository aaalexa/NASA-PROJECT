"""Tests de motor/tendencias.py (skills motor-tendencias y validacion-y-pruebas)."""
from __future__ import annotations

import json
import math

import numpy as np
import pymannkendall as mk
import pytest
from scipy import stats

from motor import tendencias as tz
from motor.tendencias import CLAVES_SALIDA, calcular_tendencia

META = dict(variable="lluvia_gpcp", region="prueba", periodo=("2001-01", "2024-12"))


def _calc(y, t, unidad="mes", **kw):
    return calcular_tendencia(y, t, unidad_tiempo=unidad, **{**META, **kw})


# 1. Ejemplo pequeño calculado a mano ------------------------------------------------------------
def test_ols_ejemplo_a_mano():
    # t = 0..4, y = [1, 3, 2, 5, 4]: t̄ = 2, ȳ = 3
    # (t−t̄) = [−2,−1,0,1,2], (y−ȳ) = [−2,0,−1,2,1] → Σ = 4+0+0+2+2 = 8, Sxx = 10 → β₁ = 0.8, β₀ = 3 − 0.8·2 = 1.4
    t = np.arange(5.0)
    y = np.array([1.0, 3.0, 2.0, 5.0, 4.0])
    r = tz.ols(y, t)
    assert r.beta1 == pytest.approx(0.8, rel=1e-12)
    assert r.beta0 == pytest.approx(1.4, rel=1e-12)
    assert r.sxx == pytest.approx(10.0)
    np.testing.assert_allclose(r.residuos, y - (1.4 + 0.8 * t), atol=1e-12)


def test_prueba_t_coincide_con_linregress_sin_autocorrelacion():
    # Con n_ef = n, la prueba corregida debe ser exactamente la clásica de linregress.
    rng = np.random.default_rng(1)
    t = np.arange(40.0)
    y = 0.05 * t + rng.normal(size=40)
    a = tz.ols(y, t)
    p = tz.prueba_t_corregida(a.beta1, a.residuos, a.sxx, n_ef=40.0)
    ref = stats.linregress(t, y)
    assert a.beta1 == pytest.approx(ref.slope, rel=1e-10)
    assert p.se == pytest.approx(ref.stderr, rel=1e-10)
    assert p.p == pytest.approx(ref.pvalue, rel=1e-8)
    t_crit = stats.t.ppf(0.975, 38)
    assert p.ic95 == pytest.approx((ref.slope - t_crit * ref.stderr, ref.slope + t_crit * ref.stderr), rel=1e-10)


def test_n_efectivo_formula_y_cotas():
    e = np.array([1.0, 2.0, 1.5, 3.0, 2.5, 4.0, 3.0, 5.0])
    r1, n_ef = tz.n_efectivo(e)
    r1_ref = np.corrcoef(e[:-1], e[1:])[0, 1]
    assert r1 == pytest.approx(r1_ref)
    assert n_ef == pytest.approx(min(max(8 * (1 - r1_ref) / (1 + r1_ref), 3), 8))
    # r₁ ≈ 1 → acotado a 3
    _, n_alto = tz.n_efectivo(np.arange(50.0) ** 2)
    assert n_alto == pytest.approx(3.0)
    # r₁ < 0 → acotado a n
    _, n_neg = tz.n_efectivo(np.array([1.0, -1.0] * 20))
    assert n_neg == pytest.approx(40.0)


def test_sen_coincide_con_pymannkendall_con_t_regular(serie_ar1):
    t, y = serie_ar1(120, 0.02, 0.3, semilla=4)
    assert tz.pendiente_sen(y, t) == pytest.approx(mk.sens_slope(y).slope, rel=1e-12)


def test_weatherhead_formula():
    rng = np.random.default_rng(2)
    e = rng.normal(size=240)
    n_star, falt, nota = tz.anios_para_detectar(0.01, e, 0.3, 240, "mes")
    esperado = ((3.3 * np.std(e, ddof=1) / 0.12) * math.sqrt(1.3 / 0.7)) ** (2 / 3)
    assert nota is None
    assert n_star == pytest.approx(esperado, rel=1e-12)
    assert falt == pytest.approx(max(0.0, esperado - 20.0), rel=1e-12)


def test_veredicto_tabla():
    assert tz.veredicto(0.01, 0.02, -1.0) == ("significativo", "baja")
    assert tz.veredicto(0.01, 0.20, 1.0) == ("indicio", "sube")
    assert tz.veredicto(0.30, 0.04, 1.0) == ("indicio", "sube")
    assert tz.veredicto(0.30, 0.40, 0.0) == ("sin tendencia clara", "estable")
    assert tz.veredicto(0.05, 0.05, 1.0)[0] == "sin tendencia clara"  # p < α estricto


# 2. Tendencia conocida + AR(1) -------------------------------------------------------------------
def test_tendencia_conocida_dentro_del_ic(serie_ar1):
    pendiente = 0.01  # por mes → 1.2 por década
    t, y = serie_ar1(300, pendiente, 0.5, sigma=1.0, semilla=7)
    r = _calc(y, t)
    lo, hi = r["ic95_decada"]
    assert lo <= pendiente * 120 <= hi, f"1.2/década fuera del IC {r['ic95_decada']}"
    assert r["veredicto"] == "significativo"
    assert r["direccion"] == "sube"
    assert r["metodos"] == ["ols_neff", "mk_hamed_rao"]
    assert 0.3 < r["r1"] < 0.7
    assert r["n_ef"] < r["n"]


# 3. Cobertura del IC ------------------------------------------------------------------------------
@pytest.mark.lento
def test_cobertura_ic(serie_ar1):
    semillas = np.random.default_rng(123).integers(1_000_000_000, size=200)
    pendiente = 0.005
    dentro = 0
    for s in semillas:
        t, y = serie_ar1(240, pendiente, 0.5, semilla=int(s))
        a = tz.ols(y, t)
        _, n_ef = tz.n_efectivo(a.residuos)
        lo, hi = tz.prueba_t_corregida(a.beta1, a.residuos, a.sxx, n_ef).ic95
        dentro += lo <= pendiente <= hi
    cobertura = dentro / len(semillas)
    assert cobertura >= 0.90, f"cobertura del IC 95 % = {cobertura:.1%} (< 90 %)"


# 4. Falsos positivos ------------------------------------------------------------------------------
@pytest.mark.lento
def test_falsos_positivos_ruido_ar1(serie_ar1):
    semillas = np.random.default_rng(2026).integers(1_000_000_000, size=500)
    significativos = 0
    solo_t = 0
    solo_mk = 0
    for s in semillas:
        t, y = serie_ar1(240, 0.0, 0.5, semilla=int(s))
        r = _calc(y, t)
        significativos += r["veredicto"] == "significativo"
        solo_t += r["p_t"] < 0.05
        solo_mk += r["p_mk"] < 0.05
    n = len(semillas)
    tasa, tasa_t, tasa_mk = significativos / n, solo_t / n, solo_mk / n
    assert tasa <= 0.08, f"'significativo' en {tasa:.1%} de series de ruido puro (máx. 8 %)"
    assert tasa_t <= 0.10, f"prueba t significativa en {tasa_t:.1%} de series de ruido (máx. 10 %)"
    # Hamed-Rao sola es liberal (~15 % medido, ver referencia §4); este límite detecta si empeora.
    assert tasa_mk <= 0.20, f"Mann-Kendall significativa en {tasa_mk:.1%} de series de ruido (máx. 20 %)"


# 5. Casos límite ----------------------------------------------------------------------------------
def test_serie_constante():
    r = _calc(np.full(60, 3.0), np.arange(60.0))
    assert r["pendiente_ols_decada"] == 0.0
    assert r["p_t"] == 1.0
    assert r["p_mk"] == 1.0
    assert r["veredicto"] == "sin tendencia clara"
    assert r["direccion"] == "estable"
    assert r["snr"] is None
    assert r["n_star_anios"] is None and "n_star_indefinido" in r["metodos"]
    json.dumps(r, allow_nan=False)


def test_nan_se_descartan(serie_ar1):
    t, y = serie_ar1(120, 0.02, 0.2, semilla=3)
    y_nan = y.copy()
    y_nan[[5, 50, 99]] = np.nan
    r = _calc(y_nan, t)
    r_ref = _calc(np.delete(y, [5, 50, 99]), np.delete(t, [5, 50, 99]))
    assert r["n"] == 117
    assert r["pendiente_ols_decada"] == pytest.approx(r_ref["pendiente_ols_decada"])
    assert r["sen_decada"] == pytest.approx(r_ref["sen_decada"])


def test_serie_corta_usa_mk_original():
    r = _calc([1.0, 2.0, 1.5, 3.0, 2.8, 3.5, 4.0], np.arange(7.0))
    assert "mk_original" in r["metodos"] and "mk_hamed_rao" not in r["metodos"]
    assert r["n"] == 7


def test_serie_demasiado_corta_falla():
    with pytest.raises(ValueError, match="demasiado corta"):
        _calc([1.0, 2.0, np.nan, 3.0, 4.0], np.arange(5.0))


def test_serie_anual_y_factor_decada():
    anios = np.arange(2001, 2025, dtype=float)
    y = 2.0 * (anios - 2001) + np.sin(anios)  # ~2 por año
    r_anual = calcular_tendencia(y, anios, unidad_tiempo="anio", variable="cdd_imerg", region="x",
                                 periodo=("2001", "2024"))
    b1 = tz.ols(y, anios).beta1
    assert r_anual["pendiente_ols_decada"] == pytest.approx(b1 * 10)
    assert r_anual["n_star_anios"] is None and r_anual["anios_faltantes"] is None
    assert "n_star_no_aplica_anual" in r_anual["metodos"]
    # La misma serie leída como mensual multiplica por 120 y sí calcula n*.
    r_mes = _calc(y, anios - 2001)
    assert r_mes["pendiente_ols_decada"] == pytest.approx(b1 * 120)
    assert r_mes["n_star_anios"] is not None


def test_cambio_pct_y_snr(serie_ar1):
    t, y = serie_ar1(240, -0.02, 0.3, semilla=11)
    r = _calc(y, t, media_climatologia=80.0)
    assert r["cambio_pct_decada"] == pytest.approx(100 * r["pendiente_ols_decada"] / 80.0)
    assert r["snr"] == pytest.approx(r["pendiente_ols_decada"] / np.std(y, ddof=1))
    assert r["direccion"] == "baja"
    assert _calc(y, t)["cambio_pct_decada"] is None


def test_unidad_tiempo_invalida():
    with pytest.raises(ValueError, match="unidad_tiempo"):
        calcular_tendencia(np.arange(10.0), np.arange(10.0), unidad_tiempo="dia", **META)


# 6. Esquema JSON ------------------------------------------------------------------------------------
def test_esquema_json(serie_ar1):
    t, y = serie_ar1(504, -0.01, 0.2, sigma=5.0, semilla=5)
    r = _calc(y, t, periodo=("1983-01", "2024-12"), media_climatologia=85.0)
    assert tuple(r.keys()) == CLAVES_SALIDA
    texto = json.dumps(r, allow_nan=False)
    assert json.loads(texto) == r
    assert isinstance(r["n"], int) and r["n"] == 504
    assert all(type(v) in (int, float, str, list, type(None)) for v in r.values())
    assert r["periodo"] == ["1983-01", "2024-12"]
    assert r["veredicto"] in ("significativo", "indicio", "sin tendencia clara")
    assert r["direccion"] in ("sube", "baja", "estable")
