# Referencia — fórmulas de preprocesamiento

## 1. Promedio espacial ponderado

Para cada tiempo t, con celdas i de latitud φ_i (en grados) y valor x_i(t):

```
w_i  = cos(φ_i · π/180)
V(t) = { i : x_i(t) no es NaN  y  la celda está en la región/máscara }
x̄(t) = Σ_{i∈V(t)} w_i · x_i(t) / Σ_{i∈V(t)} w_i
fraccion_area_valida(t) = Σ_{i∈V(t)} w_i / Σ_{i∈región} w_i
si fraccion_area_valida(t) < min_area_valida (0.9) → x̄(t) = NaN
```

Con fracción de polígono f_i (de `mask_3D_frac_approx`), el peso es `w_i · f_i`.

```python
w = np.cos(np.deg2rad(da["lat"]))
if fraccion is not None:
    w = w * fraccion            # DataArray (lat, lon)
serie = da.weighted(w.fillna(0)).mean(("lat", "lon"), skipna=True)
peso_total = (w * da.notnull().any("time")).sum(("lat", "lon"))      # celdas de la región
peso_valido = (w * da.notnull()).sum(("lat", "lon"))
serie = serie.where(peso_valido / peso_total >= min_area_valida)
serie.attrs = {**da.attrs}      # conservar units
```

(Las celdas fuera de la región ya son NaN tras el recorte o la máscara, así que no cuentan en `peso_total`.)

## 2. Climatología y anomalías

```
C_m = media{ x̄(t) : t en el periodo base, mes(t) = m },   m = 1..12
y_t = x̄(t) − C_{mes(t)}
media_climatologia = (1/12) · Σ_m C_m          → se pasa al motor para el cambio %
```

```python
base = serie.sel(time=slice(*periodo_base))
clim = base.groupby("time.month").mean("time")
anom = serie.groupby("time.month") - clim
anom = anom.drop_vars("month")
```

Exige al menos ~80 % de años válidos por mes en el periodo base; si un mes tiene muy pocos, la climatología de ese
mes es poco fiable: repórtalo.

## 3. Agregación anual

| tipo de variable | unidad mensual | método | unidad anual |
|---|---|---|---|
| lluvia (cantidad) | mm/mes | suma de 12 meses | mm/anio |
| lluvia (tasa) | mm/dia | primero × días del mes → mm/mes, luego suma | mm/anio |
| temperatura, humedad, vapor, NDVI, evaporación (tasa) | degC, mm, 1, mm/dia | media de 12 meses | igual |

```python
conteo = serie.groupby("time.year").count("time")
if metodo == "suma":
    anual = serie.groupby("time.year").sum("time", skipna=False)
else:
    anual = serie.groupby("time.year").mean("time", skipna=False)
anual = anual.where(conteo == 12).rename(year="anio")
```

## 4. Control de calidad

```
calendario = pd.date_range(inicio, fin, freq="MS")      (mensual) o años inicio..fin (anual)
serie = serie.reindex(time=calendario)
n_esperados = len(calendario)
n_faltantes = cuenta de NaN
fraccion_faltante = n_faltantes / n_esperados
aceptada = fraccion_faltante <= 0.10
```

Si se rechaza: `raise SerieRechazada(f"{variable} en {region}: {100*fraccion:.1f} % de datos faltantes (máximo 10 %)", reporte)`.
El escáner captura esta excepción y muestra la variable como "datos insuficientes", sin ocultarla.

## 5. Entrada del motor

```python
def preparar_para_motor(serie, media_climatologia=None) -> dict:
    if "time" in serie.dims:              # mensual
        fechas = pd.DatetimeIndex(serie["time"].values)
        t = (fechas.year - fechas.year[0]) * 12 + (fechas.month - fechas.month[0])   # meses desde el inicio
        unidad = "mes"; periodo = (fechas[0].strftime("%Y-%m"), fechas[-1].strftime("%Y-%m"))
    else:                                 # anual, dim 'anio'
        t = serie["anio"].values.astype(float); unidad = "anio"
        periodo = (str(int(t[0])), str(int(t[-1])))
    return {"y": serie.values.astype(float), "t": np.asarray(t, float), "unidad_tiempo": unidad,
            "periodo": periodo, "media_climatologia": media_climatologia}
```

Los NaN se pasan tal cual: el motor descarta los pares inválidos y cuenta `n` con los válidos.
