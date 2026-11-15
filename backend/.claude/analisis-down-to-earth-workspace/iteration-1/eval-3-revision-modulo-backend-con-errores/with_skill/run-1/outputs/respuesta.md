# Revisión de `modulo_backend_simulado.py` (tendencias de la pantalla de resultados)

**Respuesta corta: no está bien hecho estadísticamente.** La estructura es la correcta (OLS anual + HAC + IC +
corrección múltiple), pero tiene seis errores que cambian los números o las etiquetas que ve el público, y varios
más de robustez. Dos de ellos son graves por sí solos: la temperatura sale unas 12 veces más grande de lo real
(+4.53 °C/década en vez de +0.38), y los meses que faltan se convierten en meses con lluvia 0 y temperatura 0 °C.

La versión corregida está en `tendencias_demo_corregido.py` (misma carpeta). La comprobé contra el script de
referencia de la skill (`analisis_dte.py`) con los dos CSV simulados de prueba: pendientes, IC, p sin ajustar,
p de Holm y etiquetas coinciden con las del script para las cuatro variables. Más abajo están los números.

---

## Problemas encontrados (por línea y gravedad)

| # | Línea | Gravedad | Problema | Por qué está mal | Corrección |
|---|---|---|---|---|---|
| 1 | 22 | **Crítica** | `df.fillna(0)` | Un hueco de la descarga pasa a ser un mes con 0 mm de lluvia, 0 °C o humedad 0: un mes extremo que nunca ocurrió. Ese año queda "seco" o "frío" y arrastra la pendiente. | Dejar NaN. El año con algún mes faltante queda **incompleto** (NaN) para esa variable. |
| 2 | 27 | **Crítica** | `.groupby(year).sum()` para las cuatro variables | Sumar temperaturas (°C) o humedades (m³/m³) no tiene sentido físico: la T anual sale ≈ 250 "°C" y la SM ≈ 2.5 "m³/m³". Las pendientes de T y SM quedan multiplicadas por ~12 (se muestra +4.53 °C/década). Además `sum()` salta los NaN, así que un año con 11 meses también se sumaría. | P y ET: **suma** de 12 meses (mm/año). T y SM: **media ponderada por días reales** Σ(X·días)/Σ(días) con `calendar.monthrange`. `min_count=12`: un mes faltante → año NaN. |
| 3 | 37 | Alta | `maxlags: 3` como rezago principal | El método fija el rezago 1 de antemano. Usar 3 (o elegir el rezago "que mejor salga") convierte el p en una decisión que depende de los datos. Con 24 años, además, amplía el IC sin justificación. | `maxlags=1` como principal. Los rezagos 2 y 3 se calculan **solo como sensibilidad** (con Holm completo) y, si cambian la decisión, la etiqueta añade "; resultado sensible al rezago". |
| 4 | 44 | **Crítica** | `p * 10  # por década` | El p-valor no depende de la unidad de tiempo: z = b/SE no cambia al pasar de "por año" a "por década", porque b y SE se multiplican por 10. Multiplicar p por 10 lo infla 10 veces y puede dar p > 1. | Solo pendiente e IC × 10. **El p se publica tal cual.** |
| 5 | 55 | Alta | Bonferroni sobre `len(visibles)` | (a) La familia de pruebas la define la pregunta (las cuatro variables), no lo que el usuario deja marcado: con el mismo dato, la etiqueta cambia según la pantalla. (b) Bonferroni es más conservador de lo necesario; Holm controla el mismo error y es uniformemente más potente. | **Holm sobre la familia fija [P, T, SM, ET]** siempre (`multipletests(..., method="holm")`). `visibles` solo filtra lo que se devuelve. Variable no evaluable: null + motivo, y p = 1 interno para Holm (no se publica). |
| 6 | 59 | Alta | `etiqueta = "sin cambio"` cuando p > 0.05 | Ausencia de evidencia no es evidencia de ausencia. Con p ajustado > 0.05 solo se puede decir que, con estos años y este método, la pendiente no se distingue de la variación natural. | "evidencia insuficiente" (o "evidencia insuficiente tras el ajuste" si el p sin ajustar era ≤ 0.05). Las positivas: "aumento/disminución con evidencia estadística según este método". |
| 7 | 18–20 | Media | No se reindexa a un calendario mensual completo y la fecha no se normaliza a año-mes | Si falta una fila (un mes no descargado), ese año se agrega con 11 meses sin aviso. Las fechas con día u hora distintos o las duplicadas no se detectan. | Normalizar a `Period("M")`, reindexar a un calendario completo (los ausentes quedan como NaN) y tratar los duplicados con valores distintos como faltantes, con una advertencia. |
| 8 | 34 + 51 | Media | Sin tramo común: cada variable usa todos sus años, incluidos los incompletos | Las cuatro tendencias deben describir el mismo período para que se puedan comparar. Además, con el `fillna(0)` actual, los años con huecos se cuelan en el ajuste. | Tramo común más largo de años completos y consecutivos (empate → el más reciente), el mismo para las cuatro y sin comprimir huecos. Se informa inicio, fin y n. |
| 9 | 20 | Baja | Solo se trata `-9999` como relleno | −999, 9.999e20 y valores ≥ 1e15 (relleno habitual de NASA) pasarían como datos válidos. | Relleno → NaN: `≤ −999`, `|x| ≥ 1e15` y no finitos. |
| 10 | 35–45 | Baja | Sin protección ante un SE de 0 (serie sin variación residual) ni ante series demasiado cortas | Saldrían p = 0 o NaN y una etiqueta sin sentido. | Si SE = 0 o no es finito: pendiente sin inferencia (IC y p en null, con motivo). Con < 3 años: null + motivo. Advertencia si hay < 10 años. |
| 11 | 61–64 | Baja | La salida no incluye el p sin ajustar, el período usado, n de años ni advertencias. La unidad "mm/década" de P y ET es ambigua | La pantalla no puede mostrar la plantilla completa ("…; IC95 %; p ajustado; etiqueta. Período …, n años válidos"). | Se añaden `p_sin_ajustar`, `n_anios`, `anios_incompletos`, `sensibilidad` y `_metadata` (tramo, método, advertencias). La unidad pasa a "mm por década (total anual)". El formato sigue la guía: P/ET con 1 decimal, T con 2, SM con 4. |

Lo que sí estaba bien y se conserva: OLS con constante, t en años reales desde el año inicial, kernel Bartlett,
`use_correction=True`, `use_t=False` (Wald normal) y la pendiente e IC × 10.

---

## Efecto en los números (datos simulados de prueba)

### CSV completo (`dte_simulado_completo.csv`, 2001–2024, sin huecos), datos simulados

| Var. | Original: cambio / p mostrado / etiqueta | Corregido (= script de referencia) |
|---|---|---|
| P | −32.5 mm/década · p = 1 · "sin cambio" | −32.5 mm/década; IC95 % [−99.8, +34.8]; p = 0.343; p Holm = 0.343; evidencia insuficiente |
| T | **+4.53 °C/década** · p = 1.7e-6 · "aumento" | **+0.38 °C/década**; IC95 % [+0.21, +0.54]; p Holm < 0.001; aumento con evidencia estadística según este método |
| SM | **−0.104 m³/m³/década** · "disminución" | **−0.0086 m³/m³/década**; IC95 % [−0.0103, −0.0070]; p Holm < 0.001; disminución con evidencia estadística según este método |
| ET | −23.5 mm/década · p = 1 · "sin cambio" | −23.5 mm/década; IC95 % [−54.9, +7.9]; p = 0.142; p Holm = 0.284; evidencia insuficiente |

Aquí las decisiones coinciden por casualidad, pero T y SM salen ~12 veces más grandes. El p de P y ET aparece como
1 por el ×10 y el ×4, en lugar de 0.343 y 0.284, y los IC son más anchos por el rezago 3.

### CSV con huecos (el de unidades originales, convertido; con filas desordenadas y el mes 2013-06 ausente del archivo), datos simulados

Con huecos (T 2001-03 de relleno, mes 2013-06 ausente, SM 2024-11 vacío), el módulo original rellena con ceros y
ajusta con 24 años, mientras que el método correcto usa el tramo común completo **2002–2012 (11 años)**:

| Var. | Original | Corregido (= script de referencia) |
|---|---|---|
| T | +6.08 °C/década · p = 0.004 · **"aumento"** | +0.09 °C/década; IC95 % [−0.19, +0.37]; p Holm = 1.000; **evidencia insuficiente** |
| SM | −0.125 m³/m³/década · p = 1e-10 | −0.0087 m³/m³/década; IC95 % [−0.0138, −0.0035]; p Holm = 0.004; disminución con evidencia estadística según este método |
| P, ET | "sin cambio" | evidencia insuficiente (p Holm = 1.000 en ambas) |

Aquí la etiqueta de T cambia. Una precisión para ser justos: parte de la diferencia viene de que el tramo válido es
más corto (11 años en lugar de 24), no solo de los ceros. Aun así, la cifra del original (+6.08 °C/década) no es
válida: suma temperaturas e incluye meses inventados a 0 °C.

**Dependencia de la pantalla:** en ese mismo caso, si el usuario deja marcadas solo T y SM, el original publica
para T un p ajustado de 0.0022 en vez de 0.0045. El corregido da el mismo valor se muestre lo que se muestre.

---

## Notas sobre la versión corregida

- **Interfaz**: `resultados_pantalla(df, visibles)` se mantiene y conserva las claves `cambio`, `ic95`,
  `p_ajustado` y `etiqueta`. Cambios para el front:
  - `ic95`, `p_ajustado` y `etiqueta` pueden ser `null`, con `motivo_null`.
  - La etiqueta trae el texto completo.
  - Se añaden campos nuevos y una clave `_metadata`. Si el front recorre todas las claves del diccionario,
    tiene que saltarse `_metadata`.
  - `calcular_tendencias(df)` devuelve el cálculo completo (incluida la tabla anual).
- **Comunicación en la demo**:
  - "Evidencia insuficiente" no se puede traducir en pantalla como "estable" ni "sin cambio".
  - Muestra las cuatro variables, también las no concluyentes.
  - Puede pasar que un IC individual no incluya 0 y la etiqueta sea "evidencia insuficiente tras el ajuste". Es
    coherente: el IC es individual y Holm corrige por las cuatro pruebas.
- **Alcance de esta revisión**: el módulo recibe la serie regional ya promediada, así que no pude revisar cómo se
  hace ese promedio (debería ponderar por el área de cada celda dentro del polígono). Tampoco cubre el análisis
  conjunto (correlaciones), que este módulo no calcula.
- **Verificación**: para comprobar el módulo dentro del backend, compara su salida con la del script de la skill
  sobre el mismo CSV (`analisis_dte.py ENTRADA.csv --salida DIR`).

*Todas las cifras de esta revisión salen de datos simulados de prueba; no describen ninguna región real.*
