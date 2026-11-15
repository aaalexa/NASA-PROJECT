# Down to Earth: resumen del análisis de la región de demo (2001-2024)

> **Datos SIMULADOS.** Sirven para probar el flujo de análisis. No describen el clima real de ninguna región.

## Datos

| Variable | Unidad mensual | Agregado anual | Media anual |
|---|---|---|---|
| P, precipitación | mm/mes | suma (mm/año) | 483 mm/año |
| T, temperatura | °C | media | 21,2 °C |
| SM, humedad del suelo | m³/m³ | media | 0,199 m³/m³ |
| ET, evapotranspiración | mm/mes | suma (mm/año) | 465 mm/año |

- Hay 288 meses (2001-01 a 2024-12), sin huecos, nulos ni duplicados. Todos los valores están en rangos físicamente plausibles.
- La región tiene un régimen monzónico: la lluvia se concentra entre mayo y septiembre, con un pico en julio de unos 100 mm/mes. De octubre a abril la ET supera a la P.

## 1. ¿Hay tendencia?

Calculamos la tendencia sobre las **anomalías mensuales**, es decir, después de quitar el ciclo estacional. Usamos dos pruebas independientes:
- regresión lineal (MCO) con corrección por autocorrelación (n efectivo);
- Mann-Kendall modificado (Hamed-Rao) con pendiente de Sen.

Una tendencia es **significativa** solo cuando las dos pruebas dan p < 0,05 con el mismo signo.

| Variable | Tendencia por década (IC 95 %) | p (MCO) | p (MK) | Cambio 2001→2024 | Veredicto |
|---|---|---|---|---|---|
| **T** | **+0,38 °C** (+0,20 a +0,56) | 0,0001 | <0,0001 | +0,87 °C (+4 %) | **Significativa: se calienta** |
| **SM** | **−0,0086 m³/m³** (−0,0106 a −0,0066) | <0,0001 | <0,0001 | −0,020 m³/m³ (−10 %) | **Significativa: se seca el suelo** |
| ET | −2,0 mm/mes (−4,3 a +0,4) | 0,10 | 0,016 | −54 mm/año (−12 %) | Indicio de descenso, no concluyente |
| P | −2,7 mm/mes (−7,8 a +2,4) | 0,30 | 0,17 | −75 mm/año (−15 %) | No significativa |
| P − ET | −0,7 mm/mes (−3,7 a +2,2) | 0,62 | 0,47 | — | No significativa |

La serie anual da los mismos veredictos. Para ET, ninguna de las dos pruebas es significativa a escala anual (p ≈ 0,12-0,14).

**Cómo leerlo:**
- La **temperatura sube** unas cuatro décimas por década y la **humedad del suelo baja** un 10 % en 24 años. Las dos señales son claras: la relación señal/ruido es 4 en T y 8,5 en SM.
- La **lluvia** parece bajar (−15 %), pero su variabilidad de año a año es tan grande que ese descenso **no se distingue del azar**. Con la variabilidad actual harían falta unos 50 años de datos para confirmarlo.
- La **ET** muestra un descenso que solo una de las dos pruebas detecta. Lo presentamos como indicio, no como hallazgo.

## 2. ¿Cómo se relacionan las variables?

Correlaciones entre anomalías mensuales. La significancia está ajustada por autocorrelación.

| Par | r | Lectura |
|---|---|---|
| P – ET | **+0,95** | Fuerte. La ET sigue a la lluvia: la región está limitada por agua. |
| SM – ET | +0,56 | Moderada. Con más agua en el suelo hay más evapotranspiración. |
| P – SM | +0,54 | Moderada. La lluvia recarga el suelo en el mismo mes, con un efecto residual al mes siguiente (r = 0,19). |
| T – SM | **−0,36** | Débil-moderada y negativa. Los meses más cálidos tienen el suelo más seco, y el efecto dura hasta 3 meses. |
| P – T | +0,15 | Muy débil. |
| T – ET | +0,07 | Nula. La temperatura no controla la ET; la controla el agua disponible. |

- **Modelo de humedad del suelo:** las anomalías de P y T juntas explican el 50 % de la variación de SM. La lluvia sube SM (β estandarizado +0,61) y el calor la baja (−0,45). Los dos efectos son significativos.
- **Modelo de ET:** P sola explica casi toda la variación de ET (R² = 0,91). Una vez se tiene en cuenta la lluvia, SM no aporta información adicional.
- **Advertencia para la demo:** con los datos brutos, T y SM aparecen *positivamente* correlacionadas (r = +0,84). Es un artefacto: las dos suben en verano. Por eso todas las correlaciones de este resumen se calculan sobre anomalías.

## 3. Mensaje para la demo

> En esta región simulada, **la temperatura sube unos 0,4 °C por década y el suelo pierde un 10 % de humedad en 24 años**, y las dos tendencias son estadísticamente sólidas. La lluvia no muestra un cambio significativo. El calentamiento seca el suelo incluso sin un descenso claro de la lluvia. La evapotranspiración depende sobre todo de la lluvia, así que no "compensa" el calor.

## Archivos

- `resultados.json`: todos los resultados (calidad de los datos, climatología, tendencias mensuales y anuales, correlaciones, desfases, regresiones y balance).
- `serie_anual.csv`: serie anual (P y ET en suma, T y SM en media, P−ET y meses válidos).
- `climatologia_mensual.csv`: medias de cada mes del año.
- `graficas/`: 8 gráficas HTML interactivas (Plotly):
  - series mensuales;
  - anomalías con su tendencia;
  - series anuales con MCO y Sen;
  - climatología;
  - matriz de correlación;
  - dispersión por pares;
  - desfases;
  - balance P−ET.
- `analisis.py`: script reproducible (`python analisis.py <csv> <carpeta_salida>`).
