# Referencia — fórmulas exactas del motor de tendencias

Notación: `y_t` serie (anomalías mensuales o serie anual), `t` eje de tiempo en la unidad `u ∈ {mes, anio}`,
`n` número de pares válidos (sin NaN), barra = media aritmética. Logaritmos y raíces en float64.

## Índice
0. Limpieza de la entrada
1. Mínimos cuadrados (OLS)
2. Autocorrelación y n efectivo
3. Prueba t corregida e IC 95 %
4. Mann-Kendall (Hamed-Rao, con alternativa)
5. Pendiente de Sen
6. Escalado a década y cambio %
7. Años para detectar (Weatherhead et al., 1998)
8. Fuerza de la señal (SNR)
9. Veredicto y dirección
10. Esquema de salida
11. Casos degenerados

---

## 0. Limpieza

```
válido = isfinite(y) & isfinite(t)
y, t = y[válido], t[válido];  ordenar por t
n = len(y);  si n < 5 → ValueError("serie demasiado corta")
```

## 1. OLS

Modelo: `y_t = β₀ + β₁·t + ε_t`

```
Sxx = Σ (t − t̄)²
β₁  = Σ (t − t̄)(y − ȳ) / Sxx            [unidades de y por unidad de t]
β₀  = ȳ − β₁·t̄
e_t = y_t − (β₀ + β₁·t)                   residuos
```

## 2. Autocorrelación lag-1 de los residuos y n efectivo

```
r₁ = corr(e[0:n−1], e[1:n])               coeficiente de Pearson (np.corrcoef)
       si std(e) == 0 → r₁ = 0
n_ef = n · (1 − r₁) / (1 + r₁)
n_ef = clip(n_ef, 3, n)                   acotado: nunca < 3 ni > n
```

(Si `r₁ = −1`, la división es infinita: el `clip` la deja en `n`. Si `r₁ → 1`, n_ef → 0 y el `clip` la deja en 3.)

## 3. Prueba t corregida e IC 95 %

```
s²  = Σ e_t² / (n_ef − 2)                 OJO: n_ef − 2, no n − 2
SE  = s / √Sxx                            = √s² / √Sxx
t   = β₁ / SE
gl  = n_ef − 2                            (puede ser no entero: scipy lo admite)
p_t = 2 · scipy.stats.t.sf(|t|, gl)       bilateral
t_crit = scipy.stats.t.ppf(0.975, gl)
IC95(β₁) = [β₁ − t_crit·SE,  β₁ + t_crit·SE]
```

Con `n_ef = 3`, `gl = 1` (la distribución t tiene colas muy anchas y la prueba casi nunca es significativa,
que es lo correcto cuando la serie es casi una sola onda).

## 4. Mann-Kendall

Principal: `pymannkendall.hamed_rao_modification_test(y, alpha=alfa)` → namedtuple con
`trend, h, p, z, Tau, s, var_s, slope, intercept`. Se usan `z → mk_z`, `Tau → mk_tau`, `p → p_mk`.

Alternativa (añadir `"mk_original"` a `metodos` en vez de `"mk_hamed_rao"`):
`pymannkendall.original_test(y, alpha=alfa)` cuando

- `n < 10` (Hamed-Rao estima autocorrelaciones de los rangos y con tan pocos datos es inestable), o
- Hamed-Rao lanza una excepción, o
- su `p` no es finito (puede pasar si la varianza corregida sale ≤ 0).

MK trabaja sobre el **orden** de los datos (índices 0..n−1), no sobre `t`. Con huecos es una aproximación aceptada.

**Tasa real de falsos positivos (medida el 2026-11-13, pymannkendall 1.4.3, 500 series de ruido AR(1) con φ = 0.5, α = 0.05):**

| prueba | n = 240 | n = 504 |
|---|---|---|
| `hamed_rao_modification_test` (por defecto) | 14.8 % | 12.6 % |
| `hamed_rao_modification_test(lag=1)` | 11.0 % | 10.0 % |
| `yue_wang_modification_test` | 52.6 % | 48.8 % |
| `trend_free_pre_whitening_modification_test` | 32.4 % | 32.8 % |
| `original_test` (sin corrección) | 24.4 % | 25.0 % |
| prueba t corregida por n_ef (§3) | 5.4 % | — |
| **veredicto "significativo" (t y MK a la vez)** | **5.2 %** | — |

Consecuencias: (1) MK sola es liberal con ruido autocorrelacionado, así que un "indicio" que venga **solo** de MK es
evidencia débil, y la interfaz no debe presentarlo como hallazgo; (2) la alternativa `original_test` no corrige la
autocorrelación y solo debe usarse con series muy cortas, siempre anotada; (3) exigir las dos pruebas devuelve la
tasa al ~5 % nominal, que es la razón de ser del veredicto doble. Si se cambia la variante de MK, repite esta medición
(`tests/test_tendencias.py::test_falsos_positivos_ruido_ar1`).

## 5. Pendiente de Sen

```
Q = mediana{ (y_j − y_k) / (t_j − t_k)  :  j > k }       [unidades de y por unidad de t]
```

Se calcula con numpy sobre todos los pares (O(n²) en memoria: n = 504 → 127 000 pares, sin problema; para
n > ~5000 usar un bucle por bloques). Con `t` regular de paso 1 coincide con `slope` de pymannkendall, lo que sirve de test.

## 6. Escalado a década y cambio %

```
k = 120  si u = "mes"          (120 meses en una década)
k = 10   si u = "anio"
pendiente_ols_decada = β₁ · k
ic95_decada          = [IC_inf · k, IC_sup · k]
sen_decada           = Q · k
cambio_pct_decada    = 100 · pendiente_ols_decada / media_climatologia
                       → None si media_climatologia es None o 0
```

## 7. Años para detectar (Weatherhead et al., 1998)

Solo para **datos mensuales** (la fórmula y la constante 3.3 están derivadas para ruido mensual AR(1)):

```
ω   = β₁ · 12                  tendencia por AÑO (unidades de y / año)
σ_N = std(e, ddof=1)           desviación de los residuos mensuales
φ   = r₁
n*  = [ (3.3 · σ_N / |ω|) · √((1 + φ) / (1 − φ)) ] ^ (2/3)     [años]
años_disponibles = n / 12
anios_faltantes  = max(0, n* − años_disponibles)
```

Interpretación: n* es cuántos años de datos harían falta para detectar una tendencia de ese tamaño (con
probabilidad 0.9 y nivel 0.05) con ese nivel de ruido. Si ya tenemos más años que n*, faltan 0.

Casos:
- `u = "anio"` → `n_star_anios = None`, `anios_faltantes = None` y añadir `"n_star_no_aplica_anual"` a `metodos`.
- `ω = 0` o `φ ≥ 1` → `None` (n* infinito o indefinido; `None` mantiene el JSON válido) y añadir `"n_star_indefinido"`.

## 8. SNR

```
σ_y = std(y, ddof=1)
snr = pendiente_ols_decada / σ_y          (adimensional, con signo)
      → None si σ_y == 0
```

## 9. Veredicto y dirección (α = 0.05 por defecto)

| p_t < α | p_mk < α | veredicto |
|---|---|---|
| sí | sí | `"significativo"` |
| sí | no | `"indicio"` |
| no | sí | `"indicio"` |
| no | no | `"sin tendencia clara"` |

Dirección por el **signo de Sen**: `Q > 0 → "sube"`, `Q < 0 → "baja"`, `Q == 0 → "estable"`.

## 10. Esquema de salida (claves exactas y en este orden)

```json
{
  "variable": "lluvia_gpcp", "region": "sahel", "periodo": ["1983-01", "2024-12"],
  "n": 504, "r1": 0.21, "n_ef": 327.4,
  "pendiente_ols_decada": -12.3, "ic95_decada": [-20.1, -4.5], "p_t": 0.002,
  "sen_decada": -11.8, "mk_z": -3.1, "mk_tau": -0.12, "p_mk": 0.002,
  "cambio_pct_decada": -4.2, "snr": -0.35,
  "n_star_anios": 18.0, "anios_faltantes": 0,
  "veredicto": "significativo", "direccion": "baja",
  "metodos": ["ols_neff", "mk_hamed_rao"]
}
```

| clave | tipo | unidades |
|---|---|---|
| variable, region | str | — |
| periodo | [str, str] | "AAAA-MM" (mensual) o "AAAA" (anual) |
| n | int | número de datos válidos |
| r1 | float | adimensional |
| n_ef | float | número efectivo de datos |
| pendiente_ols_decada, sen_decada | float | unidades de y por década |
| ic95_decada | [float, float] | unidades de y por década |
| p_t, p_mk | float | probabilidad (0–1) |
| mk_z | float | estadístico normal estándar |
| mk_tau | float | −1 a 1 |
| cambio_pct_decada | float \| None | % de la media climatológica por década |
| snr | float \| None | adimensional |
| n_star_anios | float \| None | años |
| anios_faltantes | float \| None | años (0 si ya hay suficientes) |
| veredicto | str | "significativo" \| "indicio" \| "sin tendencia clara" |
| direccion | str | "sube" \| "baja" \| "estable" |
| metodos | list[str] | "ols_neff" y "mk_hamed_rao" o "mk_original"; notas opcionales "n_star_no_aplica_anual", "n_star_indefinido" |

Todos los valores con tipos nativos de Python (convertir `np.float64` con `float()`), y la salida debe pasar
`json.dumps(resultado, allow_nan=False)`.

## 11. Casos degenerados

- **Serie constante** (todos los y iguales): β₁ = 0, e = 0, SE = 0. Definir `p_t = 1.0` si β₁ == 0
  (y `p_t = 0.0` si β₁ ≠ 0 con SE = 0, caso de ajuste perfecto); IC = [β₁·k, β₁·k]. MK: si su p no es finito,
  `p_mk = 1.0`. Veredicto "sin tendencia clara", dirección "estable", snr `None`.
- **Ajuste perfecto con pendiente** (y = a + b·t): SE = 0 → p_t = 0.0 y IC degenerado.
- **n entre 5 y 9**: OLS normal, MK original (anotado).
