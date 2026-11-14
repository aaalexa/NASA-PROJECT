# Referencia — regrillado de población e impacto

## 1. Regrillado conservando el total (asignación por centro)

Malla destino con centros `lat_j`, `lon_k` y resolución `Δlat`, `Δlon` (bordes = centros ± Δ/2). Cada celda fina i
(centro `φ_i`, `λ_i`, población `p_i`) va a la celda destino que contiene su centro:

```
j(i) = índice de la celda destino con  borde_lat_j ≤ φ_i < borde_lat_{j+1}
k(i) = índice de la celda destino con  borde_lon_k ≤ λ_i < borde_lon_{k+1}
P_jk = Σ_{i : j(i)=j, k(i)=k} p_i
```

Como cada celda fina va exactamente a una celda destino, `Σ P_jk = Σ p_i` (para las celdas finas dentro de la
extensión de la malla destino). Implementación con numpy:

```python
def regrillar_poblacion(pob: xr.DataArray, malla: xr.DataArray) -> xr.DataArray:
    """pob: personas por celda fina (lat, lon). malla: DataArray con coords lat/lon destino (ascendentes)."""
    bordes_lat = _bordes(malla["lat"].values)
    bordes_lon = _bordes(malla["lon"].values)
    lat_f, lon_f = np.meshgrid(pob["lat"].values, pob["lon"].values, indexing="ij")
    j = np.digitize(lat_f.ravel(), bordes_lat) - 1
    k = np.digitize(lon_f.ravel(), bordes_lon) - 1
    p = np.nan_to_num(pob.values.ravel(), nan=0.0)
    dentro = (j >= 0) & (j < malla.sizes["lat"]) & (k >= 0) & (k < malla.sizes["lon"])
    plano = np.bincount(j[dentro] * malla.sizes["lon"] + k[dentro], weights=p[dentro],
                        minlength=malla.sizes["lat"] * malla.sizes["lon"])
    out = xr.DataArray(plano.reshape(malla.sizes["lat"], malla.sizes["lon"]),
                       coords={"lat": malla["lat"], "lon": malla["lon"]}, dims=("lat", "lon"),
                       attrs={"units": "personas"})
    total_in = p[dentro].sum()
    if total_in > 0 and abs(out.values.sum() - total_in) / total_in > 1e-6:
        raise ValueError("El regrillado no conservó el total de población")
    return out

def _bordes(centros: np.ndarray) -> np.ndarray:
    d = np.diff(centros)
    return np.concatenate([[centros[0] - d[0] / 2], centros[:-1] + d / 2, [centros[-1] + d[-1] / 2]])
```

Atajo cuando las mallas están alineadas y la razón es entera (p. ej. 0.25° → 1°, factor 4):
`pob.coarsen(lat=4, lon=4, boundary="exact").sum()`. `boundary="exact"` falla si no divide exacto, lo cual es
preferible a perder bordes en silencio.

Para MERRA-2 (0.5° × 0.625°) la razón con GPW no es entera: usa la asignación por centro.

## 2. Población afectada

Con `s_jk` = pendiente por década, `v_jk` = código de veredicto (2, 1, 0, NaN) y `P_jk` = personas:

```
Pob_seca   = Σ P_jk · [s_jk < 0] · [v_jk = 2]
Pob_humeda = Σ P_jk · [s_jk > 0] · [v_jk = 2]
Pob_total  = Σ P_jk   (celdas de la región con dato de tendencia)
pct_seca   = 100 · Pob_seca / Pob_total
```

Versión agrícola: multiplicar además por `[f_jk ≥ umbral_cultivo]`, donde `f_jk` es la fracción de píxeles MCD12Q1
(500 m) de la celda jk con LC_Type1 ∈ {12, 14}:

```
f_jk = media de clases(LC_Type1) sobre los píxeles cuyo centro cae en la celda jk
```

(misma asignación por centro de §1, pero con `bincount` de la suma y del conteo y dividiendo una por otra).

## 3. Códigos de veredicto en mapas

| código | veredicto |
|---|---|
| 2 | significativo |
| 1 | indicio |
| 0 | sin tendencia clara |
| NaN | sin datos suficientes |

```python
CODIGO_VEREDICTO = {"significativo": 2.0, "indicio": 1.0, "sin tendencia clara": 0.0}
```
