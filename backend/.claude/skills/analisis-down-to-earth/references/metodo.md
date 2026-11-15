# Método (fijo)

Contenido: 1. Preparación · 2. Valores anuales y tramo · 3. Tendencia individual · 4. Holm · 5. Sensibilidad ·
6. Revisión · 7. Análisis conjunto · 8. Esquema JSON · 9. Pseudocódigo de referencia

## 1. Preparación

1. Promedio regional ponderado por área dentro del mismo polígono para las tres fuentes (datos.md).
2. Limpiar fechas (a año-mes), relleno (→ NaN) y unidades (conversión **una sola vez**, con días reales).
3. Reindexar a un calendario completo 2001-01 … 2024-12: los meses ausentes aparecen como NaN.
4. Unir P, T, SM y ET **por año y mes**.
5. Guardar CSV mensual.

Un faltante nunca se convierte en cero ni se interpola. Rellenar parece inocuo, pero un 0 en P o ET es un mes
extremadamente seco inventado, y una interpolación reduce la varianza y hace parecer más clara una tendencia.

### Limpieza estructural de la serie regional (igual en backend `motor/limpieza_dte.py` y en el script)

| Paso | Regla | Acción |
|---|---|---|
| Tipos y fechas | valores a float64; fechas al primer día del mes; orden cronológico | — |
| Duplicados | mismo mes, valor idéntico / distinto | se conserva uno / faltante (no se promedia) |
| No finitos | ±inf | faltante |
| Relleno | ≤ −999 o \|x\| ≥ 1e15 | faltante |
| Límites físicos (unidades finales) | P [0, 3000] mm/mes · T [−90, 60] °C · SM [0, 1] m³/m³ · ET [−50, 500] mm/mes | faltante |
| Calendario | meses ausentes en 2001-01…2024-12 | faltante |
| Ceros exactos | P, SM, ET con 0.0 exacto | se conservan y se advierten |

Cada acción se registra (fecha, variable, valor original, acción, motivo). El cálculo usa float64 sin redondear;
los decimales fijos (P y ET 2, T 3, SM 5, z 3) solo se aplican en las tablas de presentación.

## 2. Valores anuales y tramo

- P y ET (flujos, mm/mes): **suma** de los 12 meses → mm/año.
- T y SM (estados, °C y m³/m³): **media ponderada por días** Σ(Xₘ·dₘ)/Σ(dₘ), con dₘ los días reales (365 o 366
  por año). Nunca se suman.
- Si falta cualquier mes, ese año queda **incompleto** (NaN) para esa variable.
- **Tramo común**: el bloque más largo de años consecutivos en que las cuatro variables evaluables están completas.
  Empate → el más reciente. Se documenta (inicio, fin, n). Los huecos no se comprimen: 2004 y 2006 no son años
  consecutivos aunque falte 2005.
- Una variable sin ningún año completo no es evaluable: se publica null con motivo y no recorta el tramo de las
  demás.
- Guardar CSV anual.

## 3. Tendencia individual

Modelo: **X = a + b·t**, con t = año − año inicial del tramo (0, 1, 2, …; años reales).

Configuración exacta en statsmodels:

```python
import statsmodels.api as sm
res = sm.OLS(y, sm.add_constant(t)).fit(
    cov_type='HAC',
    cov_kwds={'maxlags': 1, 'kernel': 'bartlett', 'use_correction': True},
    use_t=False,
)
b, se, p = res.params[1], res.bse[1], res.pvalues[1]
lo, hi = res.conf_int(alpha=0.05)[1]
```

Equivalente numpy (lo que hace statsmodels):

- β = (X'X)⁻¹X'y, u = y − Xβ, gᵢ = xᵢ·uᵢ
- S = Σᵢ gᵢgᵢ' + Σₗ₌₁..L wₗ Σᵢ (gᵢgᵢ₋ₗ' + gᵢ₋ₗgᵢ'), con pesos de Bartlett wₗ = 1 − l/(L+1), L = maxlags
- V = (X'X)⁻¹ S (X'X)⁻¹ · n/(n − k)   (k = 2; esto es `use_correction=True`)
- SE = √V₁₁

Prueba de **Wald bilateral con aproximación normal**, H₀: b = 0, α = 0.05 fijado antes de ver resultados:

- z = b/SE
- p = 2·Φ(−|z|)
- IC95 % = b ± 1.96·SE (1.959964 exacto)

Si SE es cero o no finito (p. ej. serie perfectamente lineal), se publica la pendiente sin inferencia: `p_raw`,
`p_holm` e IC en null, con el motivo.

**Por década**: b × 10 y los dos límites del IC × 10. **El p no se multiplica**: es el mismo para "por año" y "por
década" porque z = b/SE no cambia al reescalar ambos.

Unidades finales: P y ET en **mm por década** (del total anual); T en **°C por década**; SM en **m³/m³ por
década**.

Por qué HAC: los años consecutivos se parecen entre sí (autocorrelación) y el SE clásico de OLS sería demasiado
pequeño, con p demasiado bajos. Newey–West con rezago 1 amplía el SE según la autocorrelación de los residuos.

## 4. Holm

- Familia fija: **[P, T, SM, ET]**, siempre las cuatro, aunque el usuario oculte variables en pantalla.
- `multipletests(pvals, alpha=0.05, method='holm')`.
- Variable no evaluable: se publica null con motivo y se usa **p = 1 internamente** para conservar las cuatro
  hipótesis (ese 1 no se publica).
- Holm a mano: ordena p de menor a mayor; p̃₍ᵢ₎ = máx_{j ≤ i} mín(1, (m − j + 1)·p₍ⱼ₎), m = 4.
- Control: [0.003, 0.018, 0.120, 0.400] → [0.012, 0.054, 0.240, 0.400].

Por qué una familia fija: con 4 pruebas a α = 0.05, la probabilidad de al menos un falso positivo llega a ~19 %.
Si la familia dependiera de lo que se muestra, el mismo dato tendría etiquetas distintas según la pantalla.
Holm controla ese error y es uniformemente más potente que Bonferroni.

## 5. Sensibilidad

Repetir los cuatro ajustes **y Holm** con `maxlags = 2` y `maxlags = 3`. El rezago 1 sigue siendo el principal. Si
la decisión (p_holm ≤ 0.05 o no) cambia con 2 o 3, añadir a la etiqueta "resultado sensible al rezago". Nunca
elegir el rezago que da el menor p.

## 6. Revisión (lo que HAC no arregla)

- **n de años** del tramo: con menos de ~10 años, la inferencia asintótica de HAC es poco fiable.
- **Gráfico** de la serie anual con su recta: un año extremo puede arrastrar la pendiente.
- **Residuos**: Durbin-Watson muy bajo, residuo estandarizado > 3, o medias de residuos distintas entre la
  primera y la segunda mitad → posible salto, curvatura o dato malo.
- **Fracción de área válida** estable en el tiempo.
- HAC no corrige datos malos, cambios abruptos (cambio de sensor o versión) ni un modelo lineal inadecuado. Si lo
  ves, dilo junto al resultado.

## 7. Análisis conjunto

1. **No sumar** P, T, SM y ET (unidades distintas).
2. **Quitar estación**: μₘ = media de la variable en el mes calendario m (enero…diciembre) durante 2001–2024;
   anomalía = valor − μₘ.
3. **Estandarizar**: z = (valor − μₘ)/sₘ, con sₘ la desviación estándar (ddof = 1) del mes m. Si sₘ = 0 o faltan
   datos suficientes en ese mes (el script exige ≥ 10 valores), no se calcula z (NaN).
4. **Quitar la tendencia** lineal de cada serie z con el tiempo real (año decimal), usando todos sus puntos válidos;
   quedarse con los residuos.
5. **Pearson** entre residuos en las mismas fechas (meses con ambos válidos). Si un residuo no varía → null.
6. **Solo tres pares**, mismo mes, fijados de antemano: **P–SM, T–SM, P–ET**. No probar retrasos ni quedarse con
   el mayor r.
7. Publicar **r y n** (meses comunes). Son exploratorias: **sin p y sin la palabra "significativo"**.
8. Gráfico: las anomalías z conservan las tendencias; las correlaciones las eliminan. Rotularlo.

Por qué quitar la tendencia: si T sube y SM baja por razones distintas, dos tendencias opuestas producen una
correlación negativa aunque mes a mes no tengan nada que ver.

## 8. Esquema JSON de salida

```json
{
  "metadata": {
    "region": "nombre dado por el usuario o null",
    "simulado": true,
    "periodo_solicitado": {"inicio": "2001-01", "fin": "2024-12", "n_meses": 288, "n_anios": 24},
    "tramo_tendencias": {"inicio": 2001, "fin": 2024, "n_anios": 24, "criterio": "..."},
    "metodo": {"tendencia": "...", "statsmodels": "...", "prueba": "...", "alfa": 0.05,
               "multiplicidad": {"metodo": "holm", "familia": ["P", "T", "SM", "ET"]},
               "rezago_principal": 1, "sensibilidad_rezagos": [2, 3], "implementacion": "statsmodels 0.15.0"},
    "advertencias": ["..."],
    "limites": ["..."]
  },
  "variables": [
    {
      "id": "P",
      "units": {"monthly": "mm/mes", "annual": "mm/año", "slope_decade": "mm por década (total anual)"},
      "monthly": [{"fecha": "2001-01", "valor": 15.9}],
      "annual": [{"anio": 2001, "valor": 612.3, "completo": true, "meses_faltantes": [], "en_tramo": true}],
      "slope_decade": -32.5, "ci95": [-99.8, 34.8], "p_raw": 0.343, "p_holm": 0.343,
      "label": "evidencia insuficiente", "texto": "P cambió aproximadamente ...", "motivo_null": null,
      "quality": {"n_meses_validos": 288, "meses_faltantes": [], "n_valores_relleno": 0,
                  "anios_incompletos": [], "n_anios_tramo": 24, "fraccion_area": null,
                  "residuos": {"durbin_watson": 2.1, "residuo_estandarizado_max": 2.0}, "advertencias": []},
      "sensibilidad": {"rezago_principal": 1, "resultado_sensible_al_rezago": false,
                       "rezagos": [{"maxlags": 2, "slope_decade": -32.5, "ci95": [], "p_raw": 0.3, "p_holm": 0.3}]}
    }
  ],
  "joint": {
    "standardized_anomalies": [{"fecha": "2001-01", "P": 0.4, "T": -1.1, "SM": 0.2, "ET": 0.0}],
    "pairs": [{"par": "P–SM", "r": 0.72, "n": 288, "motivo_null": null}],
    "preprocessing": {"climatologia_base": "2001–2024", "estandarizacion": "...", "quitar_tendencia": "...",
                      "nota_grafico": "...", "exploratorio": "..."}
  }
}
```

(Las cifras del ejemplo son ilustrativas.) Donde no hay resultado va `null`, nunca 0 ni una cadena vacía.

## 9. Pseudocódigo de referencia

```python
anual = {v: agregar(v, mensual[v]) for v in FAMILIA}          # suma o media ponderada; NaN si falta un mes
tramo = tramo_comun_mas_largo(anual)                          # años completos y consecutivos
for lag in (1, 2, 3):
    p_int, ajustes = [], {}
    for v in ["P", "T", "SM", "ET"]:
        aj = ols_hac(anios_tramo - anios_tramo[0], anual[v][tramo], maxlags=lag)
        ajustes[v] = aj
        p_int.append(aj.p if aj.evaluable else 1.0)           # 1.0 interno, no se publica
    p_holm = multipletests(p_int, alpha=0.05, method="holm")[1]
pendiente_decada = b * 10; ic_decada = (lo * 10, hi * 10); p_publicado = p   # p sin multiplicar
```
