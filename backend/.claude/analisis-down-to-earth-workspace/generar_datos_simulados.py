"""Genera los datos SIMULADOS de las pruebas de la skill analisis-down-to-earth (semilla fija).

- dte_simulado_completo.csv   : 2001-01..2024-12, unidades finales (mm/mes, °C, m³/m³, mm/mes), sin huecos.
- dte_simulado_originales.csv : mismas series en unidades originales (mm/día, K, kg/m², kg/m²/s) con nombres
                                de campo de NASA, un −9999 en T2M 2001-03, la fila 2013-06 ausente, SM vacía en
                                2024-11 y las filas de 2010 movidas al final (para comprobar que se une por fecha).
  Tramo esperado de tendencias: 2002–2012 (11 años; el otro tramo, 2014–2023, tiene 10).
"""
import calendar
import csv
import os
import sys

import numpy as np

DEST = sys.argv[1] if len(sys.argv) > 1 else "."
os.makedirs(DEST, exist_ok=True)
rng = np.random.default_rng(20261114)

meses = [(a, m) for a in range(2001, 2025) for m in range(1, 13)]
n = len(meses)
t = np.array([(a - 2001) + (m - 0.5) / 12 for a, m in meses])  # años desde 2001
mes = np.array([m for _, m in meses])
dias = np.array([calendar.monthrange(a, m)[1] for a, m in meses])


def ar1(phi, sd):
    e = np.zeros(n)
    for i in range(1, n):
        e[i] = phi * e[i - 1] + rng.normal(0, sd)
    return e


# Ruido interanual compartido (año a año) para que las series anuales no sean demasiado suaves
anual = {a: rng.normal() for a in range(2001, 2025)}
ruido_anual = np.array([anual[a] for a, _ in meses])

# Precipitación: estación de lluvias jun–sep, tendencia débil negativa
clim_p = 18 + 95 * np.clip(np.sin((mes - 4) / 12 * 2 * np.pi), 0, None) ** 1.5
p_anom = ar1(0.3, 0.35)
P = np.clip(clim_p * np.exp(p_anom + 0.15 * ruido_anual) * (1 - 0.006 * t), 0.4, None)
# Temperatura: tendencia clara de calentamiento
T = 21 + 5.5 * np.sin((mes - 4.5) / 12 * 2 * np.pi) + 0.032 * t + ar1(0.4, 0.45) + 0.25 * ruido_anual
# Humedad del suelo: responde a la lluvia del mes y al calor; ligera disminución
SM = (0.205 + 0.045 * np.clip(np.sin((mes - 5) / 12 * 2 * np.pi), -0.6, None)
      + 0.022 * p_anom - 0.004 * (T - (21 + 5.5 * np.sin((mes - 4.5) / 12 * 2 * np.pi)))
      - 0.0007 * t + ar1(0.5, 0.004))
# ET: sigue al agua disponible más que al calor
ET = np.clip(22 + 0.38 * P * (SM / 0.2) + ar1(0.3, 3.0) + 0.04 * t * 10 / 10, 2, None)

with open(os.path.join(DEST, "dte_simulado_completo.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["fecha", "P", "T", "SM", "ET"])
    for (a, m), p, tt, sm, et in zip(meses, P, T, SM, ET):
        w.writerow([f"{a:04d}-{m:02d}", f"{p:.3f}", f"{tt:.3f}", f"{sm:.5f}", f"{et:.3f}"])

# Unidades originales
filas = []
for (a, m), d, p, tt, sm, et in zip(meses, dias, P, T, SM, ET):
    if (a, m) == (2013, 6):
        continue  # mes ausente
    p_o = f"{p / d:.6f}"
    t_o = "-9999" if (a, m) == (2001, 3) else f"{tt + 273.15:.4f}"
    sm_o = "" if (a, m) == (2024, 11) else f"{sm * 100:.4f}"
    et_o = f"{et / (86400 * d):.6e}"
    filas.append([f"{a:04d}-{m:02d}-01", p_o, t_o, sm_o, et_o])
filas = [r for r in filas if not r[0].startswith("2010")] + [r for r in filas if r[0].startswith("2010")]
with open(os.path.join(DEST, "dte_simulado_originales.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["time", "sat_gauge_precip", "T2M", "SoilMoi0_10cm_inst", "Evap_tavg"])
    w.writerows(filas)
print("ok", DEST)
