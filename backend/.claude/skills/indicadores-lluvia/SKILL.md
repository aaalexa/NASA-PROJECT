---
name: indicadores-lluvia
description: Úsala al calcular índices de extremos de lluvia a partir de datos diarios — CDD (racha seca más larga), R20mm (días de lluvia intensa), días húmedos, PRCPTOT y SDII — por año, por píxel o por serie, con xarray vectorizado, o al escribir motor/indicadores.py y sus tests con series diarias hechas a mano.
---

# Indicadores de extremos de lluvia

## Objetivo

`motor/indicadores.py` resume la lluvia diaria `P_d` (mm/dia, normalmente IMERG diario) en índices anuales que
cuentan "las dos caras": rachas secas más largas (CDD) y días de lluvia intensa (R20mm). El resultado es una serie
anual por indicador (dimensión `anio`) que luego va al motor de tendencias como cualquier otra variable del grupo
`calculada`. Las definiciones siguen a ETCCDI.

Definiciones detalladas y casos calculados a mano: [referencia.md](referencia.md).

## Definiciones (por año, con P_d en mm/dia)

| índice | definición | unidad |
|---|---|---|
| **CDD** | racha más larga de días consecutivos con `P_d < 1 mm` | dias |
| **R20mm** | número de días con `P_d ≥ 20 mm` | dias |
| **W** (días húmedos) | número de días con `P_d ≥ 1 mm` | dias |
| **PRCPTOT** | `Σ P_d` en los días húmedos | mm/anio |
| **SDII** | `PRCPTOT / W`; NaN si `W = 0` | mm/dia |

**Rachas que cruzan el año**: por defecto **se cortan el 31 de diciembre** (cada año se calcula de forma independiente
con `groupby("time.year")`). Una sequía de noviembre a febrero cuenta como dos rachas, una en cada año. Documéntalo en
el docstring y en los textos de la app; la alternativa (asignar la racha al año en que termina) se puede añadir con un
parámetro `cortar_en_anio=False`, pero no es lo predeterminado.

Umbrales con `<` y `≥` exactos: 1 mm es húmedo, 0.999 mm es seco, 20 mm cuenta para R20mm.

## Pasos

1. Comprobar que la entrada está en `mm/dia` (`attrs["units"]`) y que la frecuencia es diaria. Si no, lanzar error:
   estos índices no tienen sentido con datos mensuales.
2. **Calidad por año**: si un año tiene más del 10 % de días faltantes, todos sus índices son NaN (misma regla que
   `preprocesamiento-series`). Dentro de un año aceptado, un día NaN **no** cuenta como seco (corta la racha) ni como
   húmedo ni suma; así no se inventan rachas.
3. Calcular las máscaras `seco = (P < 1) & P.notnull()`, `humedo = P >= 1` e `intenso = P >= 20`.
4. CDD con la técnica vectorizada de suma acumulada con reinicio (ver referencia §2) aplicada por año con
   `xr.apply_ufunc(..., input_core_dims=[["time"]], dask="parallelized")`. Sin bucles de Python sobre días ni píxeles.
5. Conteos y sumas con `groupby("time.year")`: `intenso.sum()`, `humedo.sum()`, `P.where(humedo).sum()`.
6. SDII = PRCPTOT / W con `xr.where(W > 0, PRCPTOT / W, np.nan)`.
7. Devolver un `xr.Dataset` con variables `cdd, r20mm, dias_humedos, prcptot, sdii`, dimensión `anio` (entero) y
   `attrs["units"]` en cada variable.

## API (convención del proyecto)

```python
def racha_seca_maxima(seco: np.ndarray) -> np.ndarray: ...   # núcleo numpy, eje de tiempo = último
def indicadores_anuales(pr: xr.DataArray, max_faltantes: float = 0.10) -> xr.Dataset: ...
```

Funciona igual con `pr` 1-D `(time,)` (la serie de una región) y 3-D `(time, lat, lon)` (por píxel, para mapas).
Ojo: para una **región**, primero se calculan los índices por píxel y luego se promedian (ver errores comunes).

## Errores comunes

- **Promediar la lluvia de la región y después calcular CDD**: el promedio espacial casi nunca baja de 1 mm (siempre
  llueve en algún sitio), así que la CDD sale artificialmente corta. Calcula los índices por píxel y luego promédialos
  con pesos `cos(lat)` (`preprocesamiento-series`). Si se hace al revés por rapidez, decláralo.
- **NaN como seco**: `P < 1` con NaN da False en numpy, pero `~(P >= 1)` da True: un hueco se convertiría en racha seca.
  Usa `(P < 1) & P.notnull()`.
- **`sum()` de un año todo NaN da 0**, no NaN: aplica la máscara de calidad por año después de sumar.
- **SDII con W = 0** → división por cero (`inf`). Usa `xr.where`.
- **Bucles `for` por píxel**: con 0.1° y 24 años son millones de iteraciones. Todo con operaciones de arrays.
- **Unidades**: IMERG diario V07 viene en mm/dia; si alguna fuente viniera en mm/h, convierte antes (catálogo).

## Cómo probar

`tests/test_indicadores.py` con series diarias escritas a mano (referencia §3):

- Caso A de la referencia (cinco días con lluvia en 2001): CDD = 169, R20mm = 3, W = 4, PRCPTOT = 75, SDII = 18.75.
- Un año sin lluvia: CDD = 365 (o 366 si es bisiesto), W = 0, PRCPTOT = 0, SDII = NaN.
- Racha que cruza el año: 10 días secos al final de 2001 y 5 al inicio de 2002, con lluvia alrededor. CDD de 2001
  incluye los 10 días; 2002 no hereda la racha.
- Umbrales: 1.0 mm es húmedo, 0.99 es seco, 20.0 cuenta en R20mm, 19.99 no.
- Año con 11 % de días NaN → todo NaN; con un solo NaN en medio de una racha seca, la racha se corta.
- Cubo 3-D de 2 × 2 píxeles con series distintas: cada píxel da su resultado esperado (prueba de vectorización).
