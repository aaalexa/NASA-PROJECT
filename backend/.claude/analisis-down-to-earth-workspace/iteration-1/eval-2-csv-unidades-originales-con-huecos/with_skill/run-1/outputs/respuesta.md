# Análisis Down to Earth — dte_simulado_originales.csv

> **DATOS SIMULADOS.** Las cifras sirven para probar el método. No describen ninguna región real. No me diste nombre de región, así que no le puse ninguno.

## 1. Conversión (una sola vez, con los días reales de cada mes)

| Campo NASA | Unidad original | Conversión | Resultado |
|---|---|---|---|
| `sat_gauge_precip` (GPCP) | mm/día | × días del mes | P en mm/mes |
| `T2M` (MERRA-2) | K | − 273.15 | T en °C |
| `SoilMoi0_10cm_inst` (GLDAS) | kg/m² | ÷ 100 | SM en m³/m³ |
| `Evap_tavg` (GLDAS) | kg/m²/s | × 86 400 × días del mes | ET en mm/mes |

Las magnitudes cuadran con unidades originales: T ≈ 288–301, SM ≈ 16–24, ET ≈ 1e-5. Revisé algunos meses a mano. Por ejemplo, P en enero de 2001 da 0.511854 × 31 = 15.87 mm/mes, y febrero de 2004 se convierte con 29 días.

## 2. Huecos: tenías razón

| Hueco | Qué es | Qué hice |
|---|---|---|
| **2013-06** | La fila no existe en el CSV (salta de mayo a julio) | La reconstruí en el calendario como faltante para las 4 variables |
| **2001-03, T2M** | Valor de relleno `-9999` | Lo pasé a faltante |
| **2024-11, SoilMoi0_10cm_inst** | Celda vacía | Lo dejé como faltante |

Nada se rellenó con 0 ni se interpoló. Las variables se unieron por año y mes, no por posición de fila. Un año al que le falta un mes queda **incompleto** para esa variable. Así, 2013 queda incompleto para las cuatro, 2001 para T y 2024 para SM.

## 3. Años usados

- **Período pedido:** 2001-01 a 2024-12 (24 años).
- **Años usados para las tendencias: 2002–2012, 11 años.** Es el tramo más largo de años consecutivos con las cuatro variables completas, y es el mismo para las cuatro.
  - Se excluyen 2001 (falta T de marzo), 2013 (falta junio entero) y 2024 (falta SM de noviembre).
  - 2014–2023 también está completo, pero tiene 10 años. Como el tramo debe ser continuo y el hueco de 2013 no se comprime, gana 2002–2012.
- Esto significa que las tendencias **dejan fuera 13 de los 24 años**, entre ellos toda la parte reciente. Con 11 años la inferencia HAC funciona, pero está cerca del mínimo razonable (unos 10 años). Tómalo con cautela.
- **Para las correlaciones** sí se usan todos los meses válidos de 2001–2024 (286, 285 o 287 según el par).

## 4. Tendencias por década

Método: OLS anual + HAC/Newey–West con rezago 1, prueba de Wald bilateral, α = 0.05 y ajuste de Holm sobre [P, T, SM, ET]. La etiqueta la decide el p ajustado.

| Var. | Pendiente por década | IC95 % | p sin ajustar | p ajustado (Holm) | Etiqueta |
|---|---|---|---|---|---|
| P | −73.2 mm (total anual) | [−313.5, +167.1] | 0.551 | 1.000 | evidencia insuficiente |
| T | +0.09 °C | [−0.18, +0.37] | 0.509 | 1.000 | evidencia insuficiente |
| SM | −0.0087 m³/m³ | [−0.0138, −0.0035] | < 0.001 | 0.004 | disminución con evidencia estadística según este método |
| ET | −54.9 mm (total anual) | [−178.6, +68.8] | 0.385 | 1.000 | evidencia insuficiente |

En frases:
- P cambió aproximadamente −73.2 mm por década; IC95 % [−313.5, +167.1]; p ajustado 1.000; evidencia insuficiente. Período 2002–2012, 11 años válidos.
- T cambió aproximadamente +0.09 °C por década; IC95 % [−0.18, +0.37]; p ajustado 1.000; evidencia insuficiente. Período 2002–2012, 11 años válidos.
- SM cambió aproximadamente −0.0087 m³/m³ por década; IC95 % [−0.0138, −0.0035]; p ajustado 0.004; disminución con evidencia estadística según este método. Período 2002–2012, 11 años válidos.
- ET cambió aproximadamente −54.9 mm por década; IC95 % [−178.6, +68.8]; p ajustado 1.000; evidencia insuficiente. Período 2002–2012, 11 años válidos.

Cómo leerlo:
- Los p ajustados de 1.000 no son un error. Holm multiplica cada p por el número de pruebas que le tocan y lo limita a 1. Con p sin ajustar entre 0.38 y 0.55, el resultado se satura en 1.
- El p **no** se multiplica por 10 al pasar a década. Solo se escalan la pendiente y el IC.
- "Evidencia insuficiente" **no** quiere decir que P, T o ET "no cambiaron". Quiere decir que con estos 11 años y este método no se puede distinguir su pendiente de la variación natural.
- **Sensibilidad:** con los rezagos 2 y 3 la decisión no cambia para ninguna variable (SM: p Holm 0.001 y < 0.001; las otras siguen en 1.000).
- **Residuos:** Durbin-Watson entre 1.41 y 2.18 y residuo estandarizado máximo menor que 2. No veo años atípicos ni saltos evidentes.

## 5. Correlaciones (exploratorias)

Uso anomalías z por mes calendario (base 2001–2024) a las que les quité la tendencia lineal, y Pearson en el mismo mes. Solo calculo los tres pares fijados de antemano. No llevan p-valor.

| Par | r | n (meses) | Lectura |
|---|---|---|---|
| P–SM | +0.72 | 286 | varían en el mismo sentido |
| T–SM | −0.16 | 285 | sentido opuesto, coincidencia pequeña |
| P–ET | +0.78 | 287 | varían en el mismo sentido |

- P y SM mostraron asociación mensual r = 0.72, con 286 meses, tras quitar estación y tendencia.
- T y SM mostraron asociación mensual r = −0.16, con 285 meses, tras quitar estación y tendencia.
- P y ET mostraron asociación mensual r = 0.78, con 287 meses, tras quitar estación y tendencia.

Que dos variables coincidan no significa que una cause la otra. Además, SM y ET salen del mismo modelo GLDAS Noah, que usa la lluvia como entrada, así que su relación con P no es una confirmación independiente.

## 6. Advertencias y límites

- Las tendencias cubren solo 2002–2012 (11 de 24 años), por los huecos de 2001, 2013 y 2024.
- El CSV no trae la fracción de área válida, así que no puedo comprobar que la cobertura de la región sea la misma en todo el período.
- SM es solo la capa de 0–10 cm. ET es evapotranspiración real, no potencial. T es la temperatura del aire a 2 m, no la de la superficie.
- 24 años no forman una normal climatológica de 30. P − ET no es un balance hídrico cerrado. Estos datos no sirven para clasificar sequías ni inundaciones.
- En el `resumen.md` que generó el script había una frase que decía "con 24 años" en la explicación de "evidencia insuficiente". La corregí a "11 años del tramo (2002–2012)", que es lo que realmente se usó.

## 7. Archivos generados

En `.claude/analisis-down-to-earth-workspace/iteration-1/csv-unidades-originales-con-huecos/with_skill/outputs/`:

- `mensual.csv`: las 288 fechas en unidades finales (mm/mes, °C, m³/m³, mm/mes) y las anomalías z. Los faltantes quedan vacíos.
- `anual.csv`: totales de P y ET, medias de T y SM ponderadas por días, si cada año está completo y si entra en el tramo.
- `resultados.json`: todos los resultados (metadata, tendencias, sensibilidad, calidad, correlaciones), rotulados como simulados.
- `resumen.md`: resumen en texto.
- `graficos/`: `anual_P.svg`, `anual_T.svg`, `anual_SM.svg`, `anual_ET.svg` (serie anual con su recta) y `anomalias_z.svg`.
- `respuesta.md`: esta respuesta.
