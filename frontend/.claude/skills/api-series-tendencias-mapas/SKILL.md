---
name: api-series-tendencias-mapas
description: Úsala al construir o conectar gráficas de series temporales, climatología y anomalías (/api/v1/series/{variable_id}), fichas estadísticas del motor de tendencias de 20 claves (/api/v1/tendencias/{variable_id}), indicadores anuales de extremos de lluvia con GPM IMERG diario (/api/v1/indicadores), el escáner regional ordenado por veredicto y |SNR| (/api/v1/escaner), el comparador "Las dos caras" (/api/v1/dos-caras) o los mapas de tendencia por píxel (/api/v1/mapas/{variable_id}) sobre el globo 3D (react-globe.gl / cobe).
---

# Series temporales, motor de tendencias, indicadores, escáner, dos caras y mapas

## Objetivo

Conectar las vistas analíticas avanzadas y el globo interactivo del frontend (`GlobeGlExplorer.tsx`, paneles expertos y comparadores) con los 6 endpoints científicos de `/api/v1/*`. Todos ellos comparten el mismo contrato estadístico de **20 claves** (`TendenciaMotorDTO`) producido por `core/motor/tendencias.py`.

Esquemas exactos y outputs reales de los 6 endpoints: [referencia.md](referencia.md).

## 1. Las 12 variables analizables (`variable_id`)

| `variable_id` | Grupo | Fuente | Frecuencia | Unidad | Uso principal en UI |
|---|---|---|---|---|---|
| `lluvia_gpcp` | `lluvia` | `gpcp` | `mensual` | `mm/mes` | Serie y mapa de precipitación mensual (GPCP 0.5°) |
| `lluvia_merra2` | `lluvia` | `merra2` | `mensual` | `mm/dia` | Precipitación reanálisis MERRA-2 |
| `lluvia_imerg_mes` | `lluvia` | `imerg` | `mensual` | `mm/dia` | Precipitación satelital de alta resolución (0.1°) |
| `temp_aire` | `causa` | `merra2` | `mensual` | `degC` | Temperatura del aire a 2 m |
| `vapor_agua` | `causa` | `merra2` | `mensual` | `mm` | Vapor de agua total en la columna (`TQV`) |
| `humedad_suelo` | `agua` | `gldas` | `mensual` | `m3/m3` | Humedad superficial del suelo 0–10 cm |
| `evapotranspiracion` | `agua` | `gldas` | `mensual` | `mm/mes` | Evapotranspiración real mensual |
| `cdd_imerg` | `calculada` | `imerg` | `anual` | `dias` | Racha seca más larga del año ($P_d < 1\text{ mm}$) |
| `r20mm_imerg` | `calculada` | `imerg` | `anual` | `dias` | Días de lluvia muy intensa ($P_d \ge 20\text{ mm}$) |
| `dias_humedos_imerg` | `calculada` | `imerg` | `anual` | `dias` | Días con lluvia útil ($P_d \ge 1\text{ mm}$, $W$) |
| `prcptot_imerg` | `calculada` | `imerg` | `anual` | `mm/anio` | Lluvia acumulada en días húmedos ($\text{PRCPTOT}$) |
| `sdii_imerg` | `calculada` | `imerg` | `anual` | `mm/dia` | Intensidad simple diaria ($\text{SDII} = \text{PRCPTOT}/W$) |

> Nota: `lluvia_imerg_dia` existe en `/api/v1/variables`, pero tiene `analizable: false` porque es la serie diaria cruda a partir de la cual se calculan los 5 indicadores anuales. Usa `?solo_analizables=true` al poblar selectores.

## 2. Contrato de las 20 claves de tendencia (`TendenciaMotorDTO`)

Aparece en:
- `GET /api/v1/tendencias/{variable_id}` → `response.tendencia`
- `GET /api/v1/indicadores` → `response.indicadores[k].tendencia` y `response.dos_caras_extremos.region_a / region_b`
- `GET|POST /api/v1/escaner` → cada elemento de `response.resultados[]`
- `GET|POST /api/v1/dos-caras` → `response.region_a` y `response.region_b`

Claves esenciales para la interfaz:
- `pendiente_ols_decada` (`number`) e `ic95_decada` (`[number, number]`): cambio lineal por década y su intervalo de confianza al 95 % corregido por tamaño muestral efectivo (`n_ef`).
- `sen_decada` (`number`): pendiente robusta de Theil-Sen por década.
- `p_t` (`number`) y `p_mk` (`number`): p-valores bilaterales de la prueba $t$ corregida y de Mann-Kendall Hamed-Rao.
- `veredicto`: **`"significativo"`** (ambas pruebas $\le \alpha$ y mismo signo) | **`"indicio"`** (solo una $\le \alpha$) | **`"sin tendencia clara"`**.
- `direccion`: **`"sube"`** | **`"baja"`** | **`"estable"`**.
- `cambio_pct_decada` (`number | null`): porcentaje de cambio por década respecto a `media_climatologia`.
- `snr` (`number | null`): relación señal/ruido; sirve para ordenar qué variable cambia con más claridad.
- `n_star_anios` y `anios_faltantes` (`number | null`): años necesarios según Weatherhead et al. (1998) para detectar la tendencia con probabilidad 0.90 (solo en series mensuales).

## 3. Cómo graficar cada endpoint en el frontend

### A. Gráfica de serie + recta OLS (`GET /api/v1/tendencias/{variable_id}?incluir_serie=true`)
- Eje X: `puntos[i].fecha` (`"2001-01"` o `"2001"`).
- Serie de valores absolutos: `puntos[i].valor`.
- Serie de anomalías: `puntos[i].anomalia`.
- Recta de tendencia OLS sobre las anomalías:
  $$\hat{y}(t) = \text{metadatos.recta\_ols.beta0} + \text{metadatos.recta\_ols.beta1\_por\_paso} \times \text{puntos}[i].t$$
  (si graficas valores absolutos, suma `metadatos.media_climatologia` a $\hat{y}(t)$).

### B. Las dos caras de los extremos en una misma región (`GET /api/v1/indicadores`)
- Devuelve los 5 indicadores anuales (`cdd_imerg`, `r20mm_imerg`, `dias_humedos_imerg`, `prcptot_imerg`, `sdii_imerg`) con su `serie: [{ anio, valor }]` y su `tendencia`.
- Incluye `dos_caras_extremos`, que compara automáticamente **`cdd_imerg` (sequía) vs `r20mm_imerg` (lluvia torrencial)** en la misma región.

### C. Comparador "Las dos caras" (`GET` o `POST /api/v1/dos-caras`)
- Permite dos modos:
  1. **Dos regiones con la misma variable**: `variable="lluvia_gpcp"`, `region_a="sahel"`, `region_b="sureste_mexico"`.
  2. **Dos variables en la misma región**: `variable="r20mm_imerg"`, `variable_b="cdd_imerg"`, `region_a="noreste_mexico"`, `region_b="noreste_mexico"`.
- La bandera `response.dos_caras === true` se activa únicamente cuando `signo_opuesto === true` **y** `ambas_significativas === true` (ambos veredictos son `"significativo"`).

### D. Mapa de tendencias por píxel en el globo (`GET /api/v1/mapas/{variable_id}`)
- Devuelve vectores 1D `lat` (`n_lat`) y `lon` (`n_lon`), y matrices 2D `[i_lat][j_lon]` para `pendiente_decada`, `p_t`, `p_mk` y `veredicto` (`2.0` = significativo, `1.0` = indicio, `0.0` = sin tendencia clara, `null` = sin datos).
- Para convertir a puntos de `react-globe.gl` (`htmlElementsData`, `pointsData` o `heatmap`):
  ```ts
  const cells = [];
  for (let i = 0; i < mapa.lat.length; i++) {
    for (let j = 0; j < mapa.lon.length; j++) {
      const slope = mapa.pendiente_decada[i][j];
      const verdict = mapa.veredicto[i][j];
      if (slope === null || verdict === null) continue;
      cells.push({
        lat: mapa.lat[i],
        lng: mapa.lon[j], // ¡Ojo! react-globe.gl usa lng, el backend usa lon
        slope,
        verdict, // 2 = significativo, 1 = indicio, 0 = sin tendencia clara
      });
    }
  }
  ```

## Errores comunes

- **Esconder `rechazadas` en `/api/v1/escaner`**: si una variable tiene demasiados NaN aparece en `response.rechazadas: [{ variable, motivo }]`. Muéstrala en gris con el motivo ("datos insuficientes") en vez de ocultarla silenciosamente.
- **Pedir `/api/v1/mapas/lluvia_imerg_mes` en una caja gigante**: IMERG tiene resolución `0.1° × 0.1°`; si la región supera `NASA_MAX_PIXELES` (20 000 celdas), el backend devolverá `400 parametro_invalido`. Para cajas grandes usa `lluvia_gpcp` (`0.5°`) o `lluvia_merra2`.

