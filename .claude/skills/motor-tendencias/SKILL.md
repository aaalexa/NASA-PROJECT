---
name: motor-tendencias
description: Úsala siempre que haya que calcular la tendencia o la significancia de una serie temporal (anomalías mensuales o serie anual) — mínimos cuadrados con corrección por autocorrelación (n efectivo), prueba t, IC 95 %, Mann-Kendall Hamed-Rao, pendiente de Sen, tasa por década, cambio %, años para detectar (Weatherhead), SNR y veredicto — o al escribir o modificar motor/tendencias.py; nunca calcules una tendencia, un p-valor o un veredicto sin ella, aunque parezca un cálculo de una línea.
---

# Motor de tendencias

## Objetivo

`motor/tendencias.py` es el corazón de "Las dos caras de la lluvia": recibe una serie `y_t` con su eje de tiempo
y devuelve **un dict JSON** con la tasa de cambio, su significancia por dos caminos independientes (prueba t
corregida y Mann-Kendall) y un veredicto en palabras. Todo lo que la app muestre sobre "¿esta región se está
secando?" sale de aquí, y de ningún otro sitio: si otra parte del código (o una IA que redacte explicaciones)
recalculara un número, la app podría contradecirse a sí misma. Por eso el motor es la única fuente de verdad.

Las fórmulas exactas, paso a paso, están en [referencia.md](referencia.md). **Léela antes de programar o cambiar
cualquier cálculo**: los detalles (acotar n_ef, gl = n_ef − 2, ×120 vs ×10) son justo donde se cuelan los errores.
Hay un esqueleto con las firmas en [scripts/plantilla_tendencias.py](scripts/plantilla_tendencias.py).

## Por qué dos pruebas y una corrección

- Las series climáticas están **autocorrelacionadas** (un mes seco suele seguir a otro seco). La prueba t clásica
  supone independencia y, con autocorrelación positiva, declara significativas tendencias que no lo son. Por eso
  se reduce el número de datos a un **n efectivo** antes de calcular el error estándar.
- Mann-Kendall es **no paramétrica** (no supone normalidad ni linealidad) y la variante de Hamed-Rao también
  corrige la autocorrelación. Exigir que ambas coincidan para decir "significativo" hace el veredicto robusto;
  si solo una lo es, se dice "indicio", que es honesto con un público no experto.

## Pasos

1. **Limpiar la entrada**: convertir `y` y `t` a `float64`, descartar los pares con NaN en cualquiera de los dos y
   ordenar por `t`. `n` es el número de pares válidos. Si `n < 5`, lanzar `ValueError` (no hay tendencia que medir).
2. **OLS**: β₀, β₁ y residuos `e_t` (referencia §1).
3. **Autocorrelación**: `r₁` de los residuos y `n_ef` acotado a [3, n] (§2).
4. **Prueba t corregida**: s², SE, t, gl, p bilateral e IC 95 % (§3).
5. **Mann-Kendall**: `pymannkendall.hamed_rao_modification_test(y)`. Si `n < 10`, si lanza una excepción o si su
   p no es finito, usar `pymannkendall.original_test(y)` y añadir `"mk_original"` a `metodos` en lugar de `"mk_hamed_rao"` (§4).
6. **Pendiente de Sen** propia, usando los valores reales de `t` (§5).
7. **Escalar a década**, cambio %, SNR, n* de Weatherhead y años faltantes (§6–§8).
8. **Veredicto y dirección** (§9).
9. **Devolver el dict** con exactamente las claves del esquema (§10), con tipos nativos de Python
   (`float`, `int`, `str`, `list`, `None`) para que `json.dumps` funcione sin trucos.

## API (convención del proyecto)

```python
def calcular_tendencia(
    y: ArrayLike, t: ArrayLike, *,
    unidad_tiempo: Literal["mes", "anio"],
    variable: str, region: str, periodo: tuple[str, str],
    media_climatologia: float | None = None,
    alfa: float = 0.05,
) -> dict: ...
```

Funciones auxiliares públicas, cada una testeable por separado: `ols`, `n_efectivo`, `prueba_t_corregida`,
`mann_kendall`, `pendiente_sen`, `anios_para_detectar`, `veredicto`.

- `t` va **en la unidad de `unidad_tiempo`**: meses (p. ej. meses desde el inicio: 0, 1, 2…) o años (2001, 2002…).
  Convertir fechas en `t` es trabajo de `motor/series.py` (`preparar_para_motor`), no del motor.
- `media_climatologia`: la media de la climatología en las **unidades originales** de la variable (p. ej. 85 mm/mes).
  Hace falta porque, con anomalías, la media de `y` es ≈ 0 y el cambio % no tendría sentido.
- **Funciones puras**: sin red, sin archivos, sin `print`, sin estado global. Así se pueden probar aisladas y
  ejecutar por píxel en paralelo (skill `escaner-y-mapas`).
- Type hints y docstring en cada función pública, indicando las unidades de entrada y de salida
  (p. ej. "pendiente_ols_decada: unidades de y por década").
- No redondear dentro del motor: redondea la interfaz al mostrar.

## Errores comunes

- **Usar `scipy.stats.linregress` y su p-valor tal cual**: no corrige la autocorrelación. Solo sirve para verificar
  β₁ en los tests.
- **gl = n − 2** en vez de **n_ef − 2**, o calcular s² dividiendo por `n − 2`: ambos deshacen la corrección.
- **No acotar n_ef**: con r₁ ≈ 1, n_ef → 0 y gl negativos; con r₁ < 0, n_ef > n. Acotar a [3, n].
- **r₁ de la serie en vez de los residuos**: la propia tendencia infla la autocorrelación.
- **×120 con datos anuales** (o ×10 con mensuales): la tasa sale 12 veces mal. El factor depende solo de `unidad_tiempo`.
- **Sen con índices cuando hay huecos**: si se quitaron NaN, j − k ya no es la distancia en tiempo; usar `t_j − t_k`.
- **Cambio % sobre la media de las anomalías**: división por ≈ 0. Usar `media_climatologia`; si no se da, `None`.
- **Infinitos o NaN en el JSON**: `json.dumps` escribe `Infinity`/`NaN`, que no son JSON válido. Usar `None`.
- **Dirección según OLS**: la dirección sale del **signo de Sen**, que es robusta a valores atípicos.
- **Tomar MK sola como prueba fuerte**: con ruido AR(1) (φ = 0.5), Hamed-Rao da ~13–15 % de falsos positivos y
  `original_test` ~25 % (medido; tabla en referencia §4). Por eso el veredicto exige las dos pruebas (~5 %), y un
  "indicio" que venga solo de MK se presenta como débil.

## Cómo probar

Sigue la skill `validacion-y-pruebas`. Como mínimo, `tests/test_tendencias.py` debe cubrir:

1. Un ejemplo pequeño calculado a mano (β₁ exacto), y β₁ igual a `scipy.stats.linregress`.
2. Tendencia conocida + ruido AR(1) con semilla fija: la pendiente real cae dentro del IC 95 % y el veredicto es "significativo".
3. Cobertura del IC: en ~200 simulaciones, el IC contiene la pendiente real en ≥ 90 % de los casos.
4. Falsos positivos: en 500 simulaciones de ruido AR(1) puro, "significativo" sale en ≤ ~5 % (tolerancia 8 %).
5. Casos límite: n_ef acotado, serie constante, NaN, serie corta (`mk_original`), serie anual (n* = None), ×10 vs ×120.
6. El dict tiene exactamente las claves del esquema y pasa por `json.dumps(..., allow_nan=False)`.

```bash
.venv/Scripts/python -m pytest tests/test_tendencias.py -q
```
