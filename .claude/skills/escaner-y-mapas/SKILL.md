---
name: escaner-y-mapas
description: Úsala al analizar muchas variables de una región a la vez (escáner ordenado por veredicto y |SNR|), al calcular tendencias por píxel con xr.apply_ufunc y dask, al comparar "las dos caras" de dos regiones (signos opuestos y ambas significativas) o al contar la población afectada (GPW regrillada conservando el total, Pob_seca/Pob_humeda, versión solo en celdas agrícolas con MCD12Q1), o al escribir motor/escaner.py.
---

# Escáner, mapas de tendencias y las dos caras

## Objetivo

`motor/escaner.py` aplica el motor de tendencias **muchas veces**: a todas las variables de una región, a cada píxel de
un mapa o a dos regiones que se comparan, y cruza el mapa con la población. No calcula estadística propia: todo
número de tendencia, p-valor o veredicto sale de `motor.tendencias` (skill `motor-tendencias`). Si aquí se
recalculara algo "más rápido", el mapa y la ficha de una región podrían contradecirse.

Fórmulas del regrillado y de la población: [referencia.md](referencia.md).

## 1. Escáner de una región

```python
def escanear_region(series: dict[str, xr.DataArray], region: str,
                    medias_climatologia: dict[str, float] | None = None) -> dict: ...
```

- Entrada: `{id_variable: serie}` ya preparada por `preprocesamiento-series` (anomalías mensuales o anual).
  Las series rechazadas por calidad llegan como `SerieRechazada` (o se capturan al prepararlas).
- Para cada serie: `preparar_para_motor` → `calcular_tendencia`.
- Orden: primero por veredicto (`significativo` → `indicio` → `sin tendencia clara`), después por `|snr|` de mayor a
  menor (`snr = None` al final).
- Devuelve `{"region": ..., "resultados": [json_motor, ...], "rechazadas": [{"variable", "motivo"}, ...]}`.
  Las rechazadas **se muestran** ("datos insuficientes"), no se esconden: el usuario debe saber que esa variable no se pudo evaluar.

## 2. Mapa de tendencias por píxel

```python
def mapa_tendencias(cubo: xr.DataArray, unidad_tiempo: str, alfa: float = 0.05) -> xr.Dataset: ...
```

1. Partir de anomalías **por píxel** (`climatologia`/`anomalias` de `series.py` funcionan en 3-D).
2. Eje de tiempo numérico `t` (como en `preparar_para_motor`).
3. Función núcleo por píxel que llama a `calcular_tendencia` y devuelve una tupla de floats
   `(pendiente_decada, p_t, p_mk, codigo_veredicto)`. Si el píxel tiene demasiados NaN (> 10 %) o el motor lanza
   `ValueError`, devuelve `(nan, nan, nan, nan)`. **No** atrapes cualquier excepción: solo las esperadas.
4. Vectorizar con:
   ```python
   cubo = cubo.chunk({"time": -1, "lat": 20, "lon": 20})      # el tiempo, en un solo bloque
   res = xr.apply_ufunc(_nucleo_pixel, cubo, kwargs={"t": t, "unidad_tiempo": unidad_tiempo, "alfa": alfa},
                        input_core_dims=[["time"]], output_core_dims=[[], [], [], []],
                        vectorize=True, dask="parallelized", output_dtypes=[float] * 4)
   ```
5. Armar un `xr.Dataset` con `pendiente_decada` (unidades de la variable por década), `p_t`, `p_mk` y `veredicto`
   (código: 2 = significativo, 1 = indicio, 0 = sin tendencia clara, NaN = sin datos), con `attrs` que documenten
   los códigos, la variable, el periodo y α.
6. Guardar en caché: `data/cache/mapa_<variable>_<region>_<inicio>_<fin>.zarr` (misma regla de nombre y escritura
   atómica que `nasa-acceso-datos`). Si existe, leerlo en vez de recalcular.

**Coste**: Hamed-Rao por píxel es caro. Antes de lanzar un mapa global, mide el tiempo con ~100 píxeles y extrapola;
aplica la máscara de tierra antes (el océano es la mitad de las celdas y no interesa) y usa `dask` con varios procesos.
No cambies a una prueba más barata solo para el mapa: el veredicto debe ser el mismo que el de la ficha de la región.

## 3. Las dos caras

```python
def comparar_dos_caras(res_a: dict, res_b: dict) -> dict: ...
```

Devuelve `{"region_a": res_a, "region_b": res_b, "signo_opuesto": bool, "ambas_significativas": bool, "dos_caras": bool}`:
- `signo_opuesto`: una `direccion` es "sube" y la otra "baja" (según la pendiente de Sen, igual que el motor).
- `ambas_significativas`: las dos con `veredicto == "significativo"`.
- `dos_caras = signo_opuesto and ambas_significativas`. Es la afirmación central de la app, así que solo es True con
  evidencia fuerte en ambos lados; con "indicio" se muestra, pero sin esta bandera.

## 4. Impacto social: población del lado seco y del lado húmedo

```python
def regrillar_poblacion(pob: xr.DataArray, malla: xr.DataArray) -> xr.DataArray: ...    # conserva el total
def poblacion_afectada(mapa: xr.Dataset, pob_malla: xr.DataArray,
                       mascara_cultivo: xr.DataArray | None = None) -> dict: ...
```

1. **Regrillar sumando** (la población es un conteo, no una densidad): cada celda fina de GPW se asigna a la celda
   del mapa que contiene su centro y se suman las personas (referencia §1). Comprobar que
   `|total_regrillado − total_original| / total_original < 1e-6` dentro de la región; si no, lanzar error.
   GPW debe ser igual o más fina que la malla del mapa.
2. `Pob_seca = Σ pop_i` en las celdas con `pendiente_decada < 0` y `veredicto == 2`;
   `Pob_humeda = Σ pop_i` con `pendiente_decada > 0` y `veredicto == 2`. Opcionalmente, las mismas sumas con
   `veredicto == 1` ("indicio") como dato aparte.
3. **Versión agrícola**: `mascara_cultivo` = fracción de píxeles MCD12Q1 de clase 12 o 14 en cada celda del mapa
   (media del booleano regrillado) ≥ `umbral_cultivo` (0.5 por defecto, documentado). Se repiten las sumas solo en esas celdas.
4. Devuelve `{"pob_seca", "pob_humeda", "pob_total_region", "pct_seca", "pct_humeda", "anio_poblacion": 2020,
   "pob_seca_agricola", "pob_humeda_agricola", "umbral_cultivo"}`, con enteros de personas.

## Convenciones

- Funciones con type hints y docstrings que indiquen unidades (`pendiente_decada` en unidades de la variable por década; población en personas).
- Ningún número de veredicto se calcula aquí: si hace falta otro campo, añádelo al motor.
- Textos para el usuario final en español y sin jerga ("zonas que se están secando", no "pendiente negativa significativa").

## Errores comunes

- **Promediar la población al regrillar** (`coarsen().mean()`): el total cambia con la resolución. Siempre suma.
- **`coarsen(boundary="trim")`** sin comprobar el total: recorta los bordes y pierde gente. Usa la asignación por centro (referencia §1).
- **Tiempo partido en varios bloques de dask** con `input_core_dims=[["time"]]`: apply_ufunc falla o, peor, calcula por trozos.
- **Atrapar todas las excepciones** en el núcleo por píxel: oculta errores reales (p. ej. unidades) detrás de un mapa lleno de NaN.
- **Contar las celdas "indicio"** como secas o húmedas en la cifra principal: infla el impacto.
- **Población de otro año** sin decirlo: anota `anio_poblacion`.

## Cómo probar

- Escáner: tres series sintéticas (tendencia fuerte, débil y ruido) salen ordenadas significativo → … → sin tendencia,
  y una serie con 20 % de NaN aparece en `rechazadas`.
- Mapa: cubo 3 × 3 con tendencias conocidas por píxel (positiva, negativa, nula); `pendiente_decada` coincide con
  `calcular_tendencia` aplicado píxel a píxel (igualdad exacta: es la misma función).
- Dos caras: combinaciones de dirección y veredicto → banderas esperadas.
- Regrillado: población aleatoria a 0.25° regrillada a 1° conserva el total (tolerancia 1e-6) y la celda gruesa
  es la suma de sus 16 celdas finas.
- Población afectada: mapa sintético con dos celdas secas significativas de 100 y 50 personas y una húmeda "indicio" → `pob_seca = 150`, `pob_humeda = 0`.
