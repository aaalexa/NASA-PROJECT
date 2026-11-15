# Cómo comunicar los resultados

El público de la demo no es estadístico. Una frase mal elegida ("no cambió", "el calor causó la sequía") se recuerda
más que la tabla. Estas reglas existen para que cada frase diga exactamente lo que el método permite decir.

## Etiquetas de tendencia (las decide el p ajustado por Holm)

| Situación | Etiqueta |
|---|---|
| p_holm ≤ 0.05 y b > 0 | "aumento con evidencia estadística según este método" |
| p_holm ≤ 0.05 y b < 0 | "disminución con evidencia estadística según este método" |
| p_holm > 0.05 y p sin ajustar ≤ 0.05 | "evidencia insuficiente tras el ajuste" |
| p_holm > 0.05 y p sin ajustar > 0.05 | "evidencia insuficiente" |
| SE cero o no finito | pendiente sin inferencia + motivo |
| no evaluable | null + motivo |
| la decisión cambia con los rezagos 2 o 3 | añadir "; resultado sensible al rezago" |

- Para la etiqueta **manda el p ajustado**, no el IC individual ni el p sin ajustar. Puede pasar que el IC95 %
  individual no incluya 0 y aun así la etiqueta sea "evidencia insuficiente tras el ajuste": es coherente, porque
  el IC es individual y Holm corrige por las cuatro pruebas.
- "Evidencia insuficiente" **no** significa "no cambió", "estable" ni "sin tendencia". Significa que, con estos
  años y este método, no se puede distinguir la pendiente de la variación natural.

## Plantillas

Tendencia:

> [Variable] cambió aproximadamente [valor y unidad] por década; IC95 % [inferior, superior]; p ajustado [valor];
> [etiqueta]. Período [fechas], [n] años válidos.

Ejemplo ilustrativo (cifras inventadas): "T cambió aproximadamente +0.38 °C por década; IC95 % [+0.21, +0.54];
p ajustado < 0.001; aumento con evidencia estadística según este método. Período 2001–2024, 24 años válidos."

Relación:

> [X] y [Y] mostraron asociación mensual r = [valor], con [n] meses, tras quitar estación y tendencia.

- Sin p-valor, sin "significativo", sin "fuerte/débil" como veredicto estadístico. Si hace falta orientar al
  lector, decir el signo ("varían en el mismo sentido" / "en sentido opuesto") y recordar que es exploratorio.
- Recordar que SM y ET salen del mismo modelo GLDAS (su relación con P no es una confirmación independiente).

Formatos: pendientes con signo; P y ET con 1 decimal, T con 2, SM con 4; p con 3 decimales ("< 0.001" si es menor).

## Definiciones correctas (úsalas tal cual o parafraseadas sin cambiar el sentido)

- **p-valor**: si la pendiente verdadera fuera cero y el modelo fuera adecuado, la probabilidad de observar una
  pendiente al menos tan alejada de cero como la obtenida. **No** es la probabilidad de que el resultado sea falso
  ni la de que H₀ sea cierta.
- **p ajustado (Holm)**: el p corregido porque se prueban cuatro variables a la vez; es el que se compara con 0.05.
- **Evidencia estadística / significancia**: que p ajustado ≤ 0.05. **No mide** el tamaño ni la importancia
  práctica del cambio: un cambio pequeño puede tener evidencia y uno grande puede no tenerla.
- **IC95 %**: el rango de pendientes compatibles con los datos según el método; si se repitiera el procedimiento
  muchas veces, ~95 % de los intervalos contendrían la pendiente verdadera. Es **individual**, no simultáneo para
  las cuatro variables, y no incluye la incertidumbre del satélite ni del modelo.
- **Correlación r**: cuánto coinciden las subidas y bajadas mensuales de dos variables después de quitar estación y
  tendencia. Coincidir no es causar.

## Frases prohibidas y su alternativa

| No decir | Decir |
|---|---|
| "P no cambió" / "sin cambio" / "estable" (con p > 0.05) | "evidencia insuficiente para afirmar un cambio" |
| "el calor causó la sequía" / "la falta de lluvia provocó…" | "T subió y SM bajó en el mismo período; los datos no muestran la causa" |
| "correlación significativa" | "asociación mensual r = …, con n meses (exploratoria)" |
| "hay sequía" / "año de inundación" | describir los valores; estos datos no clasifican eventos |
| "el balance hídrico P − ET es…" | P y ET vienen de fuentes distintas; no se restan como balance cerrado |
| "ET indica demanda atmosférica / PET" | ET es real (lo que se evaporó), limitada por el agua disponible |
| "temperatura de la superficie" | "temperatura del aire a 2 m" |
| "significativo tras el ajuste" cuando ya lo era sin ajustar | solo la etiqueta; "tras el ajuste" se usa cuando el ajuste cambió la decisión |
| "probabilidad del 95 % de que la pendiente esté en el IC" | "rango compatible con los datos según el método" |

## Qué incluir siempre

- Las cuatro variables, también las no concluyentes (omitirlas sesga la historia).
- Período pedido, tramo usado y n de años; qué años faltan y por qué, si los hay.
- Advertencias del análisis (relleno, ceros, residuos, sensibilidad, fracción de área).
- Los límites físicos de datos.md, al menos: SM 0–10 cm, ET real no PET, SM y ET comparten modelo, 24 años no son
  una normal de 30, correlación ≠ causa.
- Rótulo "datos simulados" o "ejemplo ilustrativo" cuando corresponda, también en gráficos. Si no hay nombre de
  región, no se inventa ("la región analizada").
