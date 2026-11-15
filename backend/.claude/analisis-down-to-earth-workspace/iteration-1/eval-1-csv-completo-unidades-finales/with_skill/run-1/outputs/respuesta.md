# Análisis Down to Earth: CSV simulado completo

> **DATOS SIMULADOS.** Las cifras sirven para probar el flujo; no describen ninguna región real. Como no diste
> nombre de región, aparece como "la región analizada".

Corrí el script de la skill (`analisis_dte.py --simulado`) sobre `evals/files/dte_simulado_completo.csv`. Las
unidades ya eran las finales (mm/mes, °C, m³/m³, mm/mes) y las magnitudes lo confirman (T ≈ 15–27 °C, SM ≈ 0.17–0.24,
P y ET de decenas de mm/mes), así que no se convirtió nada. La autoprueba previa pasó 25 de 25 comprobaciones
(statsmodels).

## Datos usados

- Período pedido: 2001-01 a 2024-12, 288 meses. No falta ningún mes y no hay valores de relleno ni duplicados.
- Tramo de tendencias: 2001–2024, **24 años completos**, el mismo para las cuatro variables.
- Anual: P y ET son la suma de 12 meses (mm/año); T y SM, la media ponderada por los días de cada mes.

## 1. Tendencia de cada variable

Método fijo: OLS sobre los valores anuales con errores HAC/Newey–West (rezago 1), prueba de Wald bilateral,
α = 0.05 y ajuste de Holm sobre la familia [P, T, SM, ET]. La etiqueta la decide el p ajustado.

| Variable | Cambio por década | IC95 % | p sin ajustar | p ajustado (Holm) | Resultado |
|---|---|---|---|---|---|
| P (total anual) | −32.5 mm | [−99.8, +34.8] | 0.343 | 0.343 | evidencia insuficiente |
| T (aire a 2 m) | +0.38 °C | [+0.21, +0.54] | < 0.001 | < 0.001 | aumento con evidencia estadística según este método |
| SM (0–10 cm) | −0.0086 m³/m³ | [−0.0103, −0.0070] | < 0.001 | < 0.001 | disminución con evidencia estadística según este método |
| ET (total anual) | −23.5 mm | [−54.9, +7.9] | 0.142 | 0.284 | evidencia insuficiente |

En frases para la demo:

- T cambió aproximadamente +0.38 °C por década; IC95 % [+0.21, +0.54]; p ajustado < 0.001; aumento con evidencia
  estadística según este método. Período 2001–2024, 24 años válidos.
- SM cambió aproximadamente −0.0086 m³/m³ por década; IC95 % [−0.0103, −0.0070]; p ajustado < 0.001; disminución
  con evidencia estadística según este método. Período 2001–2024, 24 años válidos.
- P cambió aproximadamente −32.5 mm por década; IC95 % [−99.8, +34.8]; p ajustado 0.343; evidencia insuficiente.
  Período 2001–2024, 24 años válidos.
- ET cambió aproximadamente −23.5 mm por década; IC95 % [−54.9, +7.9]; p ajustado 0.284; evidencia insuficiente.
  Período 2001–2024, 24 años válidos.

Cómo leerlo:

- Que P y ET tengan "evidencia insuficiente" **no** quiere decir que no cambiaron. Sus pendientes son negativas, pero
  la lluvia anual varía mucho de un año a otro (por ejemplo 682 mm en 2013 y 273 mm en 2014). Con 24 años y este
  método esa pendiente no se distingue de la variación natural, y el IC incluye tanto bajadas como subidas.
- La etiqueta de T y SM indica evidencia estadística, no el tamaño ni la importancia práctica del cambio.
- **Sensibilidad:** con los rezagos 2 y 3 la decisión no cambia para ninguna variable (p Holm de P: 0.372 y 0.367;
  de ET: 0.322 y 0.300; T y SM < 0.001 en todos los casos). El resultado principal sigue siendo el del rezago 1.
- **Residuos:** no hay años atípicos (el residuo estandarizado máximo es 2.4, en T) ni saltos claros entre las dos
  mitades del período. La recta lineal describe bien los datos.

## 2. Cómo se relacionan (exploratorio)

Usé anomalías z por mes calendario, que quitan la estación (climatología 2001–2024). Luego quité la tendencia lineal
de cada serie y calculé Pearson solo para los tres pares fijos, en el mismo mes y sin retrasos:

- P y SM mostraron asociación mensual r = 0.72, con 288 meses, tras quitar estación y tendencia. Varían en el mismo
  sentido.
- T y SM mostraron asociación mensual r = −0.16, con 288 meses, tras quitar estación y tendencia. Varían en sentido
  opuesto, con poca coincidencia.
- P y ET mostraron asociación mensual r = 0.78, con 288 meses, tras quitar estación y tendencia. Varían en el mismo
  sentido.

Estas correlaciones solo describen coincidencias, no causas, y por eso no llevan p-valor. SM y ET salen del mismo
modelo GLDAS, así que su relación con P no confirma nada de forma independiente. En el periodo, T subió y SM bajó,
pero los datos no muestran que una cosa cause la otra. Además, quitando la tendencia, la coincidencia mes a mes
entre T y SM es pequeña.

El gráfico de anomalías z **conserva** las tendencias; las correlaciones de arriba las **quitan**. Por eso el
gráfico puede verse más "alineado" que lo que indican los r.

## Advertencias y límites

- El script avisa que no recibió la fracción de área válida, así que no puede comprobar que el polígono tenga la
  misma cobertura en todo el período. Con datos simulados no importa; con datos reales conviene añadirla.
- SM es solo la capa de 0–10 cm, no la zona de raíces. ET es evapotranspiración real, no potencial (PET). T es la
  temperatura del aire a 2 m.
- 24 años no son una normal climatológica de 30 años. El IC95 % es individual para cada variable, no simultáneo para
  las cuatro, y no incluye la incertidumbre del satélite ni del modelo.
- Con estos datos no se clasifican sequías ni inundaciones, y P − ET no es un balance hídrico cerrado.

## Archivos en la carpeta de salida

`c:/Users/alexa/OneDrive/Desktop/NASA-PROJECT/backend/.claude/analisis-down-to-earth-workspace/iteration-1/csv-completo-unidades-finales/with_skill/outputs/`

- `resultados.json`: resultados completos con esquema fijo: metadatos, método, advertencias, cada variable con
  sensibilidad y residuos, y el análisis conjunto con las anomalías z.
- `anual.csv`: valores anuales (P y ET en mm/año, T en °C, SM en m³/m³) con indicadores de año completo y de
  pertenencia al tramo.
- `mensual.csv`: la serie mensual tal como se usó.
- `resumen.md`: resumen listo para la demo.
- `graficos/`: `anual_P.svg`, `anual_T.svg`, `anual_SM.svg` y `anual_ET.svg` (serie anual con su recta) y
  `anomalias_z.svg` (anomalías z con referencia 0). Todos llevan el rótulo "SIMULADO". Solo hay SVG porque no hay
  matplotlib instalado.
- `respuesta.md`: esta respuesta.
