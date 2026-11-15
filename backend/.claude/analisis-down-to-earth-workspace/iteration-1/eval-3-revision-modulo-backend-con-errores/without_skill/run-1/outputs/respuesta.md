# Revisión de `modulo_backend_simulado.py` (tendencias de la pantalla de resultados)

## Veredicto corto

**No, estadísticamente no está bien.** Tiene dos errores graves que por sí solos invalidan lo que sale en pantalla (huecos rellenados con 0 y agregación anual que suma temperaturas y humedad del suelo, incluyendo años incompletos), un error de cálculo en el p-valor (multiplicarlo por 10) y varios problemas de inferencia e interpretación. Lo comprobé con una serie sintética: la temperatura tiene una tendencia real de **+0,30 °C/década** y el módulo original muestra **−7,11 °C/década, "sin cambio"**. La versión corregida da **+0,36 °C/década (IC 95 % 0,23 a 0,48), "aumento"**, y el resto de variables, que no tenían tendencia, salen "no concluyente".

Versión corregida: `tendencias_demo_corregido.py` (en esta misma carpeta). Mantiene la firma `resultados_pantalla(df, visibles)` y las claves `cambio`, `ic95`, `p_ajustado` y `etiqueta`, así que el front no debería romperse. Añade campos nuevos.

---

## Problemas, por orden de gravedad

### 1. Los huecos se rellenan con 0 (`df.fillna(0)`): **crítico**
Un 0 es un valor físico real: 0 °C, 0 mm de lluvia, suelo completamente seco. Con esto, un mes sin datos pasa a ser un mes de helada extrema o de sequía total. Después se suma por año, así que cada hueco baja el total anual y, si los huecos caen más al principio o al final del periodo (lo habitual en descargas), **fabrica una tendencia**. El comentario dice que es "para que no se rompa el groupby", pero `groupby().sum()/mean()` ya ignora los NaN sin romperse.
**Corrección:** dejar los faltantes como NaN y controlar la completitud (punto 3).

### 2. Todas las variables se agregan con `sum()`: **crítico**
- **P y ET** (mm/mes) → suma anual en mm/año: correcto.
- **T (°C)** → sumar 12 temperaturas da "°C·mes", que no tiene sentido físico. La pendiente sale multiplicada por ~12 y, con años incompletos, se vuelve absurda.
- **SM (m³/m³)** es una fracción volumétrica, así que sumarla tampoco tiene sentido.
**Corrección:** `sum` para P y ET, `mean` para T y SM.

### 3. Se aceptan años incompletos: **grave**
Si la descarga empieza o termina a mitad de año (en la prueba, el último año llega solo hasta junio), ese año suma la mitad de meses y aparece como un año "seco" o "frío" justo en el extremo de la serie. Es justamente donde más pesa en una regresión lineal. Esto, junto con los puntos 1 y 2, es lo que convierte +0,3 °C/década en −7 °C/década.
**Corrección:** exigir 12 meses válidos por año (`MIN_MESES_POR_ANIO`) y descartar el resto. Además se reindexa a meses calendario para que un mes que falta en el archivo también cuente como hueco.

### 4. El p-valor se multiplica por 10 "por década": **error de cálculo**
```python
"p": float(res.pvalues[1]) * 10,  # por década
```
El p-valor no tiene unidades. Es el mismo si la pendiente se expresa por año o por década, porque el estadístico t no cambia al reescalar. Multiplicarlo por 10 da p-valores mayores que 1 (en la prueba, p = 4,8 para T) y hace casi imposible que algo salga significativo. Sumado a Bonferroni, la pantalla diría "sin cambio" prácticamente siempre.
**Corrección:** quitar el `* 10`. Solo la pendiente y su IC se escalan a la década.

### 5. Errores estándar HAC con aproximación normal en series cortas: **inferencia demasiado optimista**
`cov_type="HAC", maxlags=3, use_t=False` sobre unos 20 a 25 valores anuales: el estimador de Newey-West está muy sesgado hacia abajo con n tan pequeño, y usar la normal en lugar de la t lo empeora. Lo simulé con series anuales sin tendencia (n = 23, 4000 réplicas), quitando el `*10` para aislar el efecto:

| Autocorrelación AR(1) | Falsos positivos HAC + normal (original) | Falsos positivos versión corregida | Nominal |
|---|---|---|---|
| φ = 0,0 | **15,3 %** | 4,0 % | 5 % |
| φ = 0,3 | **20,6 %** | 6,2 % | 5 % |
| φ = 0,5 | **26,3 %** | 8,4 % | 5 % |

Es decir, si se arregla solo el `*10`, el método original declararía tendencia en 1 de cada 4 a 6 regiones que no la tienen.
**Corrección:** MCO con corrección por autocorrelación lag-1 de los residuos. Se usa el tamaño muestral efectivo n_eff = n(1 − r1)/(1 + r1) (Santer et al., 2000), con r1 corregido por el sesgo de muestra corta, y la distribución t con n_eff − 2 grados de libertad para el p-valor y el IC. Con autocorrelación fuerte (φ ≈ 0,5) sigue algo por encima del 5 %. Es una limitación conocida de cualquier método con ~20 años, y conviene tenerla en cuenta al leer p-valores cercanos a 0,05.
Además se calcula la **pendiente de Theil-Sen** como chequeo de robustez frente a valores atípicos. Si difiere mucho de la de MCO, conviene mirar la serie antes de enseñarla.

### 6. La corrección por comparaciones múltiples depende de lo que el usuario deja marcado: **error de diseño**
```python
p_ajustado = min(1.0, r["p"] * len(visibles))
```
Si el usuario desmarca variables en la interfaz, cambia el número de pruebas, y con él la significancia de las que quedan. **La misma tendencia de la misma región puede pasar de "sin cambio" a "aumento" por tocar una casilla.** En la prueba, el `p_ajustado` de T pasa de 0,62 con una variable visible a 1,0 con dos o con cuatro. Un resultado estadístico no puede depender de una opción de visualización.
**Corrección:** la familia de pruebas es fija: las 4 variables analizadas, siempre. `visibles` solo filtra qué se devuelve. Además, Bonferroni se sustituye por **Holm**, que controla el mismo error (FWER) y tiene más potencia.

### 7. "Sin cambio" cuando no hay significancia: **interpretación incorrecta**
No rechazar la hipótesis nula no demuestra que no haya cambio. Con unos 20 años y la variabilidad de la lluvia, una tendencia real moderada a menudo no se detecta. En una pantalla de resultados, "sin cambio" se lee como una afirmación positiva. En la prueba, P tiene un IC de −78 a +38 mm/año por década: eso no es "sin cambio", es "no sabemos".
**Corrección:** la etiqueta pasa a ser **"no concluyente"**. Se recomienda mostrar el IC junto a la etiqueta.

### 8. Unidades de la pendiente mal rotuladas: **menor, pero visible en la demo**
La serie de P y ET es un total anual (mm/año), así que la pendiente está en **mm/año por década**, no en "mm/década". T y SM, una vez promediadas, sí quedan en °C/década y m³/m³ por década.

### 9. Otros detalles menores
- **IC y p ajustado no son coherentes:** el IC es individual (sin ajustar) y la etiqueta usa el p ajustado. Puede salir un IC que excluye el 0 con la etiqueta "no concluyente". En la versión corregida se deja documentado en el campo y se devuelve también el `p` sin ajustar. Si se quiere coherencia total, habría que mostrar ICs simultáneos.
- **Sin mínimo de años:** con 3 o 4 años el módulo calcula y etiqueta igual. Ahora, con menos de 10 años válidos, devuelve `"datos insuficientes"`.
- **Validación de entrada:** las variables desconocidas en `visibles`, las columnas que faltan y las fechas duplicadas daban un `KeyError` o resultados silenciosamente erróneos. Ahora dan un error explícito.
- **Valores centinela:** solo se reemplazaba `-9999` exacto. Ahora se cubren también `-999` y los valores no numéricos.

---

## Qué devuelve ahora `resultados_pantalla`

Por variable: `cambio` (texto), `pendiente_decada`, `unidad`, `ic95`, `p`, `p_ajustado` (Holm sobre las 4 variables), `etiqueta` (`aumento` / `disminución` / `no concluyente` / `datos insuficientes`), `pendiente_sen_decada`, `n_anios`, `n_efectivo` y `periodo`.

## Cómo lo verifiqué
- Serie mensual sintética 2001–2023 con estacionalidad, T con +0,30 °C/década y el resto sin tendencia. Le añadí un hueco de 3 meses con −9999 en 2010 y la corté a mitad de 2023.
  - Original: P −55,2, T **−7,11 °C/década**, SM −0,126, ET −26,6, todas "sin cambio" (p ajustado = 1).
  - Corregido: T **+0,356 °C/década**, p ≈ 8·10⁻⁵ (Holm 3·10⁻⁴), "aumento"; Sen +0,367. P, SM y ET "no concluyente". El resultado de T es idéntico con una o con cuatro variables visibles.
- Simulación de Monte Carlo de la tasa de falsos positivos (la tabla del punto 5).

## Recomendaciones fuera del módulo
- Ojalá en la pantalla se muestre siempre el IC o una barra de error junto a la etiqueta, y el periodo y el número de años usados.
- Si la autocorrelación importa mucho (p. ej. humedad del suelo), una alternativa razonable es Mann-Kendall con corrección de Hamed-Rao más la pendiente de Sen como método principal.
- Conviene añadir tests con series sintéticas de tendencia conocida, con huecos y con años incompletos, para que estos errores no vuelvan a colarse.
