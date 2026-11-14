---
name: validacion-y-pruebas
description: Úsala al escribir tests con pytest o comprobar que los resultados del motor son correctos — series sintéticas con tendencia conocida y ruido AR(1), cobertura del IC y tasa de falsos positivos en simulaciones, tests de conversión de unidades del catálogo, tests de indicadores con series diarias hechas a mano, validación contra un CSV de NASA Giovanni (correlación ≥ 0.99) o contra estaciones NOAA GHCN — incluso si solo se pide "verificar que funciona".
---

# Validación y pruebas

## Objetivo

En un hackathon nadie revisa a mano cada número. Los tests son la prueba de que la app dice la verdad: que el motor
no declara significativas tendencias de puro ruido, que las unidades no están multiplicadas por 24 de más y que
nuestra serie coincide con la que calcula la propia NASA. Esta skill dice **qué** probar y **con qué tolerancia**,
para que los tests sean estrictos sin fallar por azar.

Generador AR(1), tolerancias y formato del CSV de Giovanni: [referencia.md](referencia.md).
Script de comparación con Giovanni: [scripts/comparar_giovanni.py](scripts/comparar_giovanni.py).

## Estructura

```
tests/
├── conftest.py               # fixtures: serie_ar1, semilla fija, cubos sintéticos pequeños
├── test_tendencias.py        # motor (skill motor-tendencias)
├── test_catalogo.py          # carga/validación y una conversión por variable
├── test_series.py            # ponderación, anomalías, agregación, control de calidad
├── test_indicadores.py       # casos a mano de indicadores-lluvia
├── test_escaner.py           # orden, apply_ufunc, dos caras, población
├── test_datos.py             # sin red: caché y normalización (con red: marcados "red")
└── validacion/               # CSV de Giovanni exportados a mano (pequeños; se pueden versionar)
pytest.ini                    # testpaths = tests; markers: lento, red
```

Ejecutar: `.venv/Scripts/python -m pytest -q` (Windows) o `python -m pytest -q`.
Omitir los lentos: `-m "not lento"`. Los de red se omiten por defecto y se activan con `-m red`.

## 1. Motor con datos sintéticos

- **Serie con pendiente conocida + ruido AR(1)** (`serie_ar1(n, pendiente, phi, sigma, semilla)`, referencia §1).
  Con semilla fija, comprueba que la pendiente real está dentro de `ic95_decada` y que el veredicto es "significativo"
  cuando la señal es clara (p. ej. SNR ≳ 1).
- **Cobertura del IC**: en ~200 simulaciones con φ = 0.5, el IC 95 % contiene la pendiente real en ≥ 90 % de los casos.
  (El 95 % nominal y la corrección aproximada de n_ef justifican el margen.)
- **Falsos positivos**: en **500** simulaciones de ruido AR(1) puro (pendiente 0, φ = 0.5), el veredicto
  "significativo" aparece en ≤ 8 % (nominal ~5 %; con 500 simulaciones la desviación típica binomial es ~1 %, así que
  8 % es ≈ 3 desviaciones). Marca este test como `@pytest.mark.lento`.
- **Semillas fijas siempre** (`np.random.default_rng(semilla)`): un test estadístico sin semilla falla de vez en cuando y
  el equipo aprende a ignorar los fallos, que es lo peor que puede pasar.
- Comparar con referencias externas cuando existan: β₁ = `scipy.stats.linregress(t, y).slope`; Sen propia =
  `pymannkendall.sens_slope(y).slope` con t regular.

## 2. Unidades

Un test por variable del catálogo con un valor calculado a mano (tabla en `catalogo-variables/referencia.md` §3),
usando `pytest.mark.parametrize` sobre los ids. Incluye febrero bisiesto y no bisiesto para `dias_del_mes`. Comprueba
también que `attrs["units"]` queda en `unidad_final`.

## 3. Indicadores

Los casos A–E de `indicadores-lluvia/referencia.md` §3, en 1-D y como cubo 2 × 2 (vectorización).

## 4. Validación contra NASA Giovanni

Giovanni (https://giovanni.gsfc.nasa.gov) calcula promedios por área de muchos productos de NASA y sirve de
"respuesta oficial" para nuestra serie.

1. En Giovanni: servicio **"Time Series, Area-Averaged"**, misma variable, misma región (bounding box) y mismo periodo.
   Descarga el CSV a `tests/validacion/<variable>_<region>_<inicio>_<fin>_giovanni.csv`.
2. Ejecuta:
   ```bash
   python .claude/skills/validacion-y-pruebas/scripts/comparar_giovanni.py \
       --giovanni tests/validacion/lluvia_imerg_mes_sahel_2001-01_2024-12_giovanni.csv \
       --serie data/cache/serie_lluvia_imerg_mes_sahel_2001-01_2024-12.nc \
       --factor 24          # convierte las unidades de Giovanni a las nuestras (IMERG mm/h → mm/dia)
   ```
3. Reporta `n`, correlación de Pearson `r`, diferencia media (nuestra − Giovanni) y RMSE. **Falla (código de salida 1)
   si r < 0.99.** Una diferencia media pequeña pero sistemática suele indicar una diferencia de máscara o de recorte de bordes.
4. `tests/test_validacion.py` envuelve el script y se **omite** (`pytest.skip`) si no existen el CSV o la caché, para
   que los tests pasen en una máquina sin datos.

Compara la serie **promediada por área antes de anomalías** (Giovanni no quita la climatología) y en las mismas unidades.

## 5. Validación opcional contra estaciones (NOAA CDO / GHCN-Daily)

- API v2 de NOAA CDO con token en la variable de entorno `NOAA_CDO_TOKEN` (nunca en el código).
- Compara la lluvia mensual de una estación con el píxel que la contiene. Un punto frente a una celda de 0.1°–0.5° no
  da r ≥ 0.99: reporta r y el sesgo como información, sin umbral que haga fallar.

## Convenciones

- Los tests no tocan la red ni `data/` salvo los marcados `red` o los que se omiten sin datos.
- Datos sintéticos pequeños y construidos en el propio test (o en `conftest.py`): se entiende qué se prueba.
- Cada `assert` con tolerancia explícita (`pytest.approx(x, rel=1e-9)` para fórmulas exactas; márgenes justificados en simulaciones).
- Los mensajes de error de los tests dicen qué número se esperaba y por qué.

## Errores comunes

- Probar solo el "camino feliz": los casos límite (NaN, serie corta, constante) son donde falla un motor estadístico.
- Comparar floats con `==`.
- Tests de simulación sin semilla, o con tolerancias tan amplias que nunca fallan (p. ej. "≤ 30 % de falsos positivos").
- Validar contra Giovanni con anomalías de un lado y valores absolutos del otro, o con unidades distintas.
