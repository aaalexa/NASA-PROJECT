El análisis está completo. La temperatura sube y la humedad del suelo baja, las dos de forma significativa. La lluvia no tiene una tendencia significativa y la evapotranspiración solo muestra un indicio de descenso.

El CSV está limpio: 288 meses (2001-01 a 2024-12), sin huecos ni nulos, y todos los valores están en rangos plausibles. La región tiene lluvias de tipo monzónico entre mayo y septiembre.

Calculé las tendencias sobre las anomalías mensuales, es decir, después de quitar el ciclo estacional. Usé dos pruebas:
- regresión lineal con corrección por autocorrelación;
- Mann-Kendall modificado (Hamed-Rao) con pendiente de Sen.

Una tendencia cuenta como significativa solo si las dos pruebas dan p < 0,05 con el mismo signo.

**¿Hay tendencia y es significativa?**

| Variable | Tendencia por década | p (lineal / MK) | Cambio 2001-2024 | Veredicto |
|---|---|---|---|---|
| T | +0,38 °C (IC 95 % +0,20 a +0,56) | 0,0001 / <0,0001 | +0,87 °C | **Significativa (sube)** |
| SM | −0,0086 m³/m³ (IC −0,0106 a −0,0066) | <0,0001 / <0,0001 | −10 % | **Significativa (baja)** |
| ET | −2,0 mm/mes | 0,10 / 0,016 | −12 % | Indicio, no concluyente |
| P | −2,7 mm/mes | 0,30 / 0,17 | −15 % | No significativa |

- La serie anual (P y ET en suma, T y SM en media) da los mismos veredictos. En la serie anual, la ET no es significativa con ninguna de las dos pruebas.
- El −15 % de la lluvia parece grande, pero queda dentro de su variabilidad natural. Con la variabilidad actual harían falta unos 50 años de datos para confirmarlo.

**¿Cómo se relacionan?** Son correlaciones entre anomalías mensuales, con la significancia ajustada por autocorrelación.

- **P–ET, r = 0,95:** la ET sigue a la lluvia, así que la región está limitada por agua. En un modelo que incluye P, T y SM, P sola explica casi toda la variación de la ET (R² = 0,91).
- **P–SM, r = 0,54:** la lluvia recarga el suelo en el mismo mes, con un efecto residual al mes siguiente.
- **SM–ET, r = 0,56:** con más agua en el suelo hay más ET.
- **T–SM, r = −0,36:** los meses más cálidos tienen el suelo más seco, y el efecto dura hasta 3 meses. P y T juntas explican el 50 % de la variación de la humedad del suelo: la lluvia la sube y el calor la baja.
- **T–ET y P–T:** son prácticamente nulas.
- **Cuidado en la demo:** con los datos brutos, T y SM salen positivamente correlacionadas (r = +0,84) porque las dos suben en verano. Es un artefacto estacional, y por eso todas las correlaciones se calcularon sobre anomalías.

**Mensaje para la demo:** el calentamiento seca el suelo aunque la lluvia no haya bajado de forma demostrable.

**Limitaciones:**
- Las gráficas son HTML interactivos de Plotly y no PNG, porque en el entorno no están instalados ni matplotlib ni kaleido. Cargan Plotly desde un CDN, así que necesitan conexión a internet para verse.
- Todos los resultados vienen de datos simulados.

**Archivos**, en `c:\Users\alexa\OneDrive\Desktop\NASA-PROJECT\backend\.claude\analisis-down-to-earth-workspace\iteration-1\csv-completo-unidades-finales\without_skill\outputs\`:
- `resultados.json`: todos los resultados (calidad de los datos, climatología, tendencias mensuales y anuales, correlaciones, desfases, regresiones y balance P−ET).
- `serie_anual.csv`
- `resumen_demo.md`: el resumen para la demo.
- `graficas\`: 8 gráficas (series mensuales, anomalías con tendencia, series anuales con MCO y Sen, climatología, matriz de correlación, dispersión por pares, desfases y balance P−ET).
- `climatologia_mensual.csv`
- `analisis.py`: script para reproducir el análisis (`python analisis.py <csv> <carpeta_salida>`).
