"""Compara nuestra serie promediada por área con un CSV exportado de NASA Giovanni.

Uso:
    python comparar_giovanni.py --giovanni tests/validacion/x_giovanni.csv --serie data/cache/serie_x.nc [--factor 24]
                                [--umbral 0.99]

--serie acepta un NetCDF (primera variable de datos, dimensión time) o un CSV con columnas time,valor.
--factor multiplica los valores de Giovanni para pasarlos a nuestras unidades (p. ej. 24 para IMERG mm/h → mm/dia).
Sale con código 1 si r < umbral, 2 si no hay datos comunes suficientes.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def leer_giovanni(ruta: Path) -> pd.Series:
    """Lee el CSV de Giovanni. Devuelve una Serie indexada por periodo mensual ('AAAA-MM') en unidades de Giovanni."""
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        filas = list(csv.reader(f))
    relleno = None
    inicio = None
    for i, fila in enumerate(filas):
        if not fila:
            continue
        if fila[0].lower().startswith("fill value") and len(fila) > 1:
            try:
                relleno = float(fila[1])
            except ValueError:
                pass
        if fila[0].strip().lower() == "time":
            inicio = i
            break
    if inicio is None:
        raise ValueError(f"{ruta}: no encuentro la fila de cabecera que empieza por 'time'")
    datos = [f for f in filas[inicio + 1:] if len(f) >= 2 and f[0].strip()]
    tiempos = pd.to_datetime([f[0] for f in datos])
    valores = np.array([float(f[1]) for f in datos])
    if relleno is not None:
        valores[np.isclose(valores, relleno)] = np.nan
    return pd.Series(valores, index=tiempos.to_period("M"), name="giovanni")


def leer_nuestra(ruta: Path) -> pd.Series:
    """Lee nuestra serie (NetCDF o CSV time,valor). Devuelve una Serie indexada por periodo mensual."""
    if ruta.suffix in (".nc", ".nc4"):
        import xarray as xr

        ds = xr.open_dataset(ruta)
        da = ds[list(ds.data_vars)[0]]
        s = da.to_series()
    else:
        df = pd.read_csv(ruta, parse_dates=[0])
        s = pd.Series(df.iloc[:, 1].values, index=df.iloc[:, 0])
    s.index = pd.DatetimeIndex(s.index).to_period("M")
    return s.rename("nuestra")


def comparar(nuestra: pd.Series, giovanni: pd.Series) -> dict:
    """Métricas de comparación en las unidades de 'nuestra'."""
    df = pd.concat([nuestra, giovanni], axis=1, join="inner").dropna()
    n = len(df)
    if n < 3:
        return {"n": n, "r": float("nan"), "dif_media": float("nan"), "rmse": float("nan")}
    dif = df["nuestra"] - df["giovanni"]
    return {
        "n": n,
        "r": float(np.corrcoef(df["nuestra"], df["giovanni"])[0, 1]),
        "dif_media": float(dif.mean()),
        "rmse": float(np.sqrt((dif**2).mean())),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--giovanni", type=Path, required=True)
    p.add_argument("--serie", type=Path, required=True)
    p.add_argument("--factor", type=float, default=1.0)
    p.add_argument("--umbral", type=float, default=0.99)
    a = p.parse_args(argv)

    g = leer_giovanni(a.giovanni) * a.factor
    s = leer_nuestra(a.serie)
    m = comparar(s, g)
    print(f"n = {m['n']}  r = {m['r']:.4f}  diferencia media = {m['dif_media']:.4g}  RMSE = {m['rmse']:.4g}")
    if m["n"] < 3:
        print("ERROR: menos de 3 meses en común; revisa periodo y fechas.")
        return 2
    if not m["r"] >= a.umbral:
        print(f"FALLA: r = {m['r']:.4f} < {a.umbral}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
