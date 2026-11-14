---
name: preprocesamiento-series
description: Úsala al convertir un cubo de datos (tiempo × lat × lon) en la serie temporal de una región — recorte por bounding box o polígono GeoJSON (regionmask/rioxarray), máscara de tierra o cultivos, promedio espacial ponderado por cos(latitud), climatología mensual, anomalías, agregación anual y control de datos faltantes — o al escribir motor/series.py o preparar la entrada del motor de tendencias.
---

# Preprocesamiento: del cubo a la serie

## Objetivo

`motor/series.py` toma el DataArray que entrega `motor/datos.py` (dims `(time, lat, lon)`, unidades finales en
`attrs["units"]`) y produce la serie de una región lista para el motor de tendencias, junto con un **reporte de
calidad**. Cada paso tiene un orden fijo porque cambiarlo cambia el resultado (p. ej. promediar antes de enmascarar
mezcla mar y tierra).

Fórmulas y detalles: [referencia.md](referencia.md).

## Pasos (en este orden)

1. **Recorte** por bounding box `(oeste, sur, este, norte)` o por polígono GeoJSON.
   - Para un polígono, recorta primero por su bounding box (rápido) y después aplica la máscara del polígono con
     `regionmask.from_geopandas(gdf).mask(da)` (o `rioxarray .rio.clip`).
   - Si ningún centro de celda cae dentro (polígono pequeño frente a celdas de 0.5°), usa
     `regionmask ... .mask_3D_frac_approx(da)` y pondera por la fracción. Si aun así no hay celdas, lanza un error
     claro; nunca devuelvas una serie de NaN sin avisar.
2. **Máscara opcional** de tierra (`regionmask.defined_regions.natural_earth_v5_0_0.land_110`) o de cultivos
   (fracción de clases 12 y 14 de MCD12Q1 en cada celda ≥ `umbral`, 0.5 por defecto). La máscara se pasa como
   DataArray booleano en la misma malla y se aplica con `da.where(mascara)`.
3. **Promedio espacial ponderado por latitud** (las celdas cerca de los polos son más pequeñas):
   `w = np.cos(np.deg2rad(da.lat))`; `serie = da.weighted(w).mean(("lat", "lon"), skipna=True)`.
   xarray excluye automáticamente el peso de las celdas con NaN. Registra además la **fracción de área válida** en
   cada paso de tiempo; si es menor que `min_area_valida` (0.9 por defecto), ese paso cuenta como faltante (NaN), porque
   un promedio hecho con media región no es comparable con los demás.
4. **Climatología mensual** `C_m` en el periodo base y **anomalías** `y_t = x̄(t) − C_{m(t)}`.
5. **Agregación anual** cuando se pida: **suma** para lluvia (solo con unidades de cantidad, `mm/mes` → `mm/anio`),
   **media** para temperatura, humedad y el resto. Solo se agregan años con los 12 meses; uno incompleto es NaN.
6. **Control de calidad**: reindexa al calendario completo (los meses ausentes aparecen como NaN) y calcula la fracción
   faltante. Si supera el 10 %, la serie se **rechaza** (`SerieRechazada`) con el motivo. **Nunca interpoles en
   silencio**: un hueco rellenado puede crear o borrar una tendencia, y el usuario no lo sabría.
7. **Preparar la entrada del motor**: `preparar_para_motor(serie)` devuelve `y`, `t`, `unidad_tiempo`, `periodo` y
   `media_climatologia`, con exactamente los argumentos que espera `motor.tendencias.calcular_tendencia`.

## Periodos

```python
PERIODO_COMUN = ("2001-01", "2024-12")   # para comparar variables entre sí (todas las fuentes lo cubren)
PERIODO_GLOBAL = ("1983-01", "2024-12")  # mapa global con GPCP / MERRA-2
```

Por defecto, el periodo base de la climatología es el mismo que el del análisis. Si se usa otro, anótalo en
`attrs["periodo_base"]`. Ojo: GPCP v3.2 termina en 2023-12 (ver `nasa-acceso-datos`).

## API (convención del proyecto)

```python
class SerieRechazada(ValueError): ...      # lleva .reporte (dict)

def recortar_bbox(da: xr.DataArray, bbox: BBox) -> xr.DataArray: ...
def recortar_poligono(da: xr.DataArray, geojson: str | Path) -> xr.DataArray: ...
def aplicar_mascara(da: xr.DataArray, mascara: xr.DataArray) -> xr.DataArray: ...
def promedio_area(da: xr.DataArray, min_area_valida: float = 0.9) -> xr.DataArray: ...   # dims (time,)
def climatologia(serie: xr.DataArray, base: tuple[str, str]) -> xr.DataArray: ...         # dims (month,)
def anomalias(serie: xr.DataArray, clim: xr.DataArray) -> xr.DataArray: ...
def agregar_anual(serie: xr.DataArray, metodo: Literal["suma", "media"]) -> xr.DataArray: ...  # dims (anio,)
def control_calidad(serie: xr.DataArray, inicio: str, fin: str, max_faltantes: float = 0.10) -> dict: ...
def preparar_para_motor(serie: xr.DataArray, media_climatologia: float | None = None) -> dict: ...
def serie_region(da, bbox_o_geojson, inicio, fin, *, mascara=None, anual=None) -> tuple[xr.DataArray, dict]: ...
```

- Las funciones funcionan con cubos 3-D y con series 1-D cuando tiene sentido (`climatologia` y `anomalias` sirven
  también por píxel para los mapas de `escaner-y-mapas`).
- Toda función conserva `attrs["units"]` (las operaciones de xarray pueden perder los attrs: usa
  `keep_attrs=True` o reasígnalos). `agregar_anual` con `suma` cambia `mm/mes` → `mm/anio`.
- Series anuales con dimensión **`anio`** (entero). Series mensuales con dimensión `time` (datetime64, día 1 de cada mes).
- `control_calidad` devuelve `{"aceptada": bool, "n_esperados": int, "n_faltantes": int, "fraccion_faltante": float, "motivo": str | None}`.

## Errores comunes

- **Promedio sin pesos** (`da.mean(("lat","lon"))`): sobrepondera las latitudes altas. Con regiones grandes la tendencia cambia.
- **Pesos que no excluyen NaN** (implementación manual `(w*x).sum()/w.sum()`): el denominador incluye celdas sin datos
  y el promedio se va hacia 0. Usa `da.weighted(w)`.
- **Sumar lluvia en mm/dia** para el total anual: 12 promedios diarios sumados no son mm/año. Convierte a mm/mes
  (× días del mes) y después suma; si la unidad no es de cantidad, `agregar_anual(..., "suma")` debe lanzar un error.
- **Anomalías con la climatología de otro periodo** sin decirlo: el desplazamiento cambia el % de cambio.
- **Meses ausentes que no aparecen como NaN**: si el archivo simplemente no tiene esa fecha, la fracción faltante sale
  0 %. Reindexa siempre a `pd.date_range(inicio, fin, freq="MS")`.
- **`interpolate_na` o `ffill`** "para que no falle el test": oculta problemas de datos. Rechaza y reporta.
- **Longitudes 0–360 o latitudes descendentes** al recortar: normaliza primero (`nasa-acceso-datos`).

## Cómo probar

- Promedio ponderado: un cubo sintético con valor 1 en el ecuador y 0 en 60° da un promedio igual a
  `cos(0)/(cos(0)+cos(60°)) = 2/3`, no 0.5.
- NaN en una celda: el promedio coincide con el de las celdas restantes.
- Climatología y anomalías: una serie `x = 10 + estacionalidad + 0.1·t` tiene anomalías sin ciclo estacional
  (la correlación con el mes es ≈ 0) y la media de las anomalías en el periodo base es 0.
- Agregación: 12 meses de 10 mm/mes → 120 mm/anio; con un mes NaN → NaN.
- Control de calidad: con 11 % de meses eliminados → `SerieRechazada`; con 9 % → aceptada y con `n_faltantes` correcto.
