# Referencia — datos sintéticos, tolerancias y formato de Giovanni

## 1. Generador de ruido AR(1) con tendencia

```
e_0 ~ N(0, σ²)                                   (arranque estacionario)
e_t = φ · e_{t−1} + η_t,   η_t ~ N(0, σ² · (1 − φ²))
y_t = β₁ · t + e_t,        t = 0, 1, …, n−1
```

Así la desviación marginal de `e` es exactamente σ, para cualquier φ.

```python
def serie_ar1(n: int, pendiente: float, phi: float, sigma: float = 1.0, semilla: int = 0
              ) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve (t, y) con t = 0..n-1 (unidad de tiempo) y y = pendiente·t + ruido AR(1)."""
    rng = np.random.default_rng(semilla)
    eta = rng.normal(0.0, sigma * np.sqrt(1 - phi**2), size=n)
    e = np.empty(n)
    e[0] = rng.normal(0.0, sigma)
    for i in range(1, n):
        e[i] = phi * e[i - 1] + eta[i]
    t = np.arange(n, dtype=float)
    return t, pendiente * t + e
```

En las simulaciones, usa un `rng` maestro que genere las semillas (`rng.integers(1e9, size=500)`) para que todo el
experimento sea reproducible con una sola semilla.

## 2. Tolerancias recomendadas

| prueba | parámetros | criterio | razón |
|---|---|---|---|
| fórmula exacta (β₁, Sen, conversiones) | — | `pytest.approx(rel=1e-9)` | aritmética determinista |
| pendiente real en IC | n = 300, φ = 0.5, señal clara | dentro del IC | un caso con semilla fija |
| cobertura del IC | 200 sim., n = 240, φ = 0.5 | ≥ 90 % | 95 % nominal; n_ef es aproximado |
| falsos positivos "significativo" | 500 sim., n = 240, φ = 0.5 | ≤ 8 % | ~5 % nominal; DE binomial ≈ 1 % |
| falsos positivos solo prueba t | 500 sim. | ≤ 10 % | la prueba t sola es algo más liberal con r₁ estimado |
| Giovanni | serie de área | r ≥ 0.99 | mismo producto, misma región |

## 3. Formato del CSV de Giovanni ("Time Series, Area-Averaged")

El CSV empieza con líneas de metadatos (`clave:,valor`) y después una fila de cabecera que empieza por `time`:

```
Title:,Area-Averaged Time Series (Region: 10W-20E, 10N-20N)
User Start Date:,2001-01-01T00:00:00Z
User End Date:,2024-12-31T23:59:59Z
Bounding Box:,"-10,10,20,20"
URL to Reproduce Results:,https://giovanni.gsfc.nasa.gov/...
Fill Value (mean_GPM_3IMERGM_07_precipitation):,-9999.9
time,mean_GPM_3IMERGM_07_precipitation
2001-01-01 00:00:00,0.0012
...
```

- El número de líneas de metadatos varía: busca la línea cuyo primer campo es `time`.
- Sustituye el valor de relleno (`Fill Value`) por NaN.
- Las unidades son las **originales** del producto (IMERG mensual en mm/h): convierte con el factor del catálogo antes de comparar.
- Alinea las fechas por mes (`AAAA-MM`): Giovanni marca el primer día del mes.

## 4. Métricas de comparación

```
n    = meses presentes en ambas series (sin NaN)
r    = correlación de Pearson
dif  = media(nuestra − giovanni)              [unidades nuestras]
rmse = √media((nuestra − giovanni)²)
falla si r < 0.99
```
