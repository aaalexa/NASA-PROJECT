# Resumen Down to Earth

> **DATOS SIMULADOS.** Las cifras sirven para probar el método; no describen ninguna región real.

Período solicitado: 2001-01 a 2024-12. Tendencias en 2002–2012 (11 años completos y consecutivos).

## 1. Cada variable por separado

Método fijo: OLS anual + errores HAC/Newey–West (rezago 1), prueba de Wald bilateral, α = 0.05, ajuste de Holm sobre P, T, SM y ET. La etiqueta la decide el p ajustado.

- P cambió aproximadamente -73.2 mm por década (total anual); IC95 % [-313.5, +167.1]; p ajustado 1.000; evidencia insuficiente. Período 2002–2012, 11 años válidos.
- T cambió aproximadamente +0.09 °C por década; IC95 % [-0.18, +0.37]; p ajustado 1.000; evidencia insuficiente. Período 2002–2012, 11 años válidos.
- SM cambió aproximadamente -0.0087 m³/m³ por década; IC95 % [-0.0138, -0.0035]; p ajustado 0.004; disminución con evidencia estadística según este método. Período 2002–2012, 11 años válidos.
- ET cambió aproximadamente -54.9 mm por década (total anual); IC95 % [-178.6, +68.8]; p ajustado 1.000; evidencia insuficiente. Período 2002–2012, 11 años válidos.

Sensibilidad al rezago (la decisión principal es la del rezago 1):

| Variable | p Holm (rezago 1) | p Holm (rezago 2) | p Holm (rezago 3) | ¿Sensible? |
|---|---|---|---|---|
| P | 1.000 | 1.000 | 1.000 | no |
| T | 1.000 | 1.000 | 1.000 | no |
| SM | 0.004 | 0.001 | < 0.001 | no |
| ET | 1.000 | 1.000 | 1.000 | no |

## 2. Las cuatro juntas (exploratorio)

Anomalías mensuales estandarizadas (sin estación), sin tendencia lineal, correlación de Pearson en el mismo mes. Describen coincidencias, no causas; no llevan p-valor.

- P y SM mostraron asociación mensual r = 0.72, con 286 meses, tras quitar estación y tendencia.
- T y SM mostraron asociación mensual r = -0.16, con 285 meses, tras quitar estación y tendencia.
- P y ET mostraron asociación mensual r = 0.78, con 287 meses, tras quitar estación y tendencia.

El gráfico de anomalías z conserva las tendencias; las correlaciones de arriba las eliminan.

## Cómo leer estos números

- **p ajustado (Holm)**: si no hubiera tendencia (b = 0) y el modelo fuera adecuado, es la probabilidad de obtener una pendiente al menos tan alejada de cero como la observada, corregida porque se prueban cuatro variables. No es la probabilidad de que el resultado sea falso.
- **Evidencia estadística** (p ajustado ≤ 0.05) no mide el tamaño ni la importancia del cambio.
- **Evidencia insuficiente** no significa "no cambió": significa que con 24 años y este método no se puede distinguir la pendiente de la variación natural.
- **IC95 %**: rango de pendientes compatibles con los datos según el método; es individual para cada variable, no simultáneo para las cuatro.

## Advertencias

- No se recibió la fracción de área válida: no se puede comprobar que el polígono tenga la misma cobertura en todo el período.
- Tendencias calculadas solo en el tramo común 2002–2012 (11 de 24 años): hay años incompletos fuera de él. Los huecos no se comprimen ni se rellenan.

## Límites

- SM describe solo la capa 0–10 cm del suelo, no la zona de raíces.
- ET de GLDAS es evapotranspiración real, no potencial: no sirve como PET para SPEI.
- SM y ET salen del mismo modelo GLDAS Noah con las mismas entradas: no son pruebas independientes entre sí.
- ET no sube necesariamente con el calor: si falta agua en el suelo puede bajar aunque T suba.
- T es temperatura del aire a 2 m (MERRA-2), no temperatura de la superficie.
- El período 2001–2024 (24 años) no es una normal climatológica de 30 años.
- Una correlación describe coincidencia temporal; no demuestra causa.
- No se clasifican sequías ni inundaciones con estos datos, y P − ET no es un balance hídrico cerrado (fuentes distintas; faltan escorrentía y almacenamiento).
- El IC95 % es individual para cada variable, no simultáneo para las cuatro, y no incluye la incertidumbre del satélite ni del modelo.
- HAC corrige la autocorrelación del error, no datos malos, cambios abruptos ni un modelo lineal inadecuado.
