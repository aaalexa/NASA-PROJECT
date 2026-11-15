# Análisis de `dte_simulado_originales.csv` (datos simulados)

Tenías razón, el CSV tiene huecos. Encontré tres. Ninguno lo rellené ni lo interpolé.

## 1. Huecos detectados

| Fecha | Variable | Qué pasaba |
|---|---|---|
| 2001-03 | T2M | Valor centinela **-9999** (si se deja, la media de 2001 baja unos 850 K) |
| 2013-06 | **las cuatro** | Falta la fila entera: el CSV salta de 2013-05 a 2013-07 |
| 2024-11 | SoilMoi0_10cm_inst | Celda vacía |

El archivo trae 287 filas para enero 2001 – diciembre 2024, cuando deberían ser 288. No hay fechas duplicadas ni otros valores fuera de rango.

**Cómo los traté:** el -9999 y la celda vacía quedan como faltantes, y el mes que no estaba se agrega como una fila vacía. Para la media anual solo cuento los años con los **12 meses válidos**. Un año al que le falta un mes queda fuera, porque perder junio, que está en plena temporada de lluvias, sesgaría la media de precipitación y de evaporación.

## 2. Conversión de unidades

| Variable | Unidad original | Conversión | Unidad final |
|---|---|---|---|
| sat_gauge_precip (GPCP) | mm/día | ninguna | mm/día |
| T2M (MERRA-2) | K | − 273.15 | °C |
| SoilMoi0_10cm_inst (GLDAS) | kg/m² | ninguna, porque 1 kg/m² equivale a 1 mm de agua en la capa de 0–10 cm (también la dejé en m³/m³ = ÷100) | kg/m² |
| Evap_tavg (GLDAS) | kg m⁻² s⁻¹ | × 86 400 | mm/día |

Después de convertir, los rangos son razonables. La precipitación media es de 1.31 mm/día (unos 480 mm/año). La temperatura va de 14.3 a 27.8 °C. La humedad del suelo va de 13 a 27 kg/m², es decir de 0.13 a 0.27 m³/m³. La evaporación media es de 1.27 mm/día.

## 3. Años usados

| Variable | Años de la tendencia | Excluidos | n |
|---|---|---|---|
| Precipitación | 2001–2024 | 2013 | 23 |
| Temperatura | 2002–2024 | 2001, 2013 | 22 |
| Humedad del suelo | 2001–2023 | 2013, 2024 | 22 |
| Evaporación | 2001–2024 | 2013 | 23 |
| **Correlaciones (periodo común)** | **2002–2023** | **2013** | **21** |

## 4. Tendencias por década (medias anuales)

Método: recta de mínimos cuadrados sobre las medias anuales. El p-valor sale de una prueba t con n efectivo corregido por la autocorrelación lag-1 de los residuos; aquí esa autocorrelación fue casi nula, así que el n efectivo queda prácticamente igual a n. Como comprobación robusta usé además Mann-Kendall y la pendiente de Sen.

| Variable | Tendencia / década | IC 95 % | **p-valor** | Sen / década | p Mann-Kendall | % / década |
|---|---|---|---|---|---|---|
| Precipitación | **−0.092 mm/día** | [−0.287, +0.103] | **0.34** | −0.094 | 0.29 | −7.1 % |
| Temperatura 2 m | **+0.36 °C** | [+0.13, +0.60] | **0.004** | +0.33 | 0.006 | — |
| Humedad suelo 0–10 cm | **−0.89 kg/m²** | [−1.06, −0.72] | **1.8 × 10⁻⁹** | −0.87 | 1.5 × 10⁻¹⁰ | −4.5 % |
| Evaporación | **−0.065 mm/día** | [−0.150, +0.019] | **0.12** | −0.060 | 0.08 | −5.2 % |

Lectura:
- **Temperatura:** calentamiento significativo de unos **+0.36 °C por década**.
- **Humedad del suelo:** secado muy significativo, de unos **−0.9 kg/m² por década** (−0.009 m³/m³ por década, −4.5 % por década). Es la señal más clara de las cuatro.
- **Precipitación y evaporación:** bajan, pero **no son significativas** (p > 0.05). Con estos datos no se distinguen de la variabilidad natural.

Hice dos comprobaciones de robustez y en las dos salen las mismas conclusiones:
- **Mismo periodo común para las cuatro (2002–2023 sin 2013):** T2M +0.39 °C/década (p = 0.005), suelo −0.84 kg/m² por década (p ≈ 0), precipitación −0.04 (p = 0.72), evaporación −0.05 (p = 0.31).
- **Anomalías mensuales (286–287 meses):** T2M +0.37 (p = 7 × 10⁻⁵), suelo −0.87 (p = 6 × 10⁻¹⁵), precipitación −0.09 (p = 0.29), evaporación −0.065 (p = 0.095).

## 5. Correlaciones (medias anuales, 2002–2023 sin 2013, n = 21)

| Par | r de Pearson | p | r sin tendencia | p | ρ de Spearman |
|---|---|---|---|---|---|
| Precipitación – Evaporación | **0.96** | 4 × 10⁻¹² | 0.97 | 2 × 10⁻¹³ | 0.95 |
| Temperatura – Humedad suelo | **−0.60** | 0.004 | −0.17 | 0.45 | −0.52 |
| Precipitación – Temperatura | **0.50** | 0.022 | 0.68 | 0.0007 | 0.56 |
| Humedad suelo – Evaporación | 0.36 | 0.11 | 0.39 | 0.08 | 0.26 |
| Temperatura – Evaporación | 0.33 | 0.14 | 0.60 | 0.004 | 0.44 |
| Precipitación – Humedad suelo | 0.20 | 0.38 | 0.32 | 0.15 | 0.16 |

Notas para interpretarlas:
- **La evaporación depende casi por completo de la lluvia** (r = 0.96). Es lo esperable en una zona semiárida, donde la evaporación está limitada por el agua que hay.
- **La correlación temperatura–suelo (−0.60) viene casi toda de las tendencias opuestas.** Una variable sube y la otra baja, y al quitarles la tendencia queda en −0.17 (p = 0.45). No conviene leerla como una relación año a año.
- **La correlación de la precipitación con el suelo es más fuerte a escala mensual** (r = 0.54 en anomalías mensuales) que anual (0.20, no significativa).
- Con n = 21, una correlación necesita |r| ≳ 0.43 para ser significativa al 5 %. Y como son 6 pares, conviene ser prudente con las que tienen p entre 0.01 y 0.05.

## 6. Archivos en la carpeta de salida

- `series_mensuales_convertidas.csv`: serie mensual completa en unidades convertidas, con los huecos como vacíos.
- `series_anuales.csv`: medias anuales; los años incompletos quedan vacíos.
- `meses_validos_por_anio.csv` y `huecos_detectados.csv`: el control de faltantes.
- `rangos_tras_conversion.csv`: estadísticos de cada variable después de convertir.
- `tendencias_por_decada.csv`: la tabla principal de tendencias.
- `tendencias_periodo_comun.csv` y `tendencias_anomalias_mensuales.csv`: las dos comprobaciones de robustez.
- `correlaciones.csv` y `matriz_correlacion_anual.csv`: las correlaciones.
- `metadatos.json`: los años del periodo común.
- `analisis.py`: el script para reproducirlo todo (`python analisis.py <csv> <carpeta_salida>`).

*Recordatorio: los datos son simulados, así que estos números sirven para probar el flujo, no para sacar conclusiones sobre la región.*
