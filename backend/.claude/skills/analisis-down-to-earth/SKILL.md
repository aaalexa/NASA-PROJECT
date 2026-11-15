---
name: analisis-down-to-earth
description: Análisis estadístico Down to Earth (NASA Space Apps) de lluvia P (GPCP sat_gauge_precip), temperatura T (MERRA-2 T2M), humedad del suelo SM (GLDAS SoilMoi0_10cm_inst) y evapotranspiración ET (GLDAS Evap_tavg) en una región, con un método fijo — tendencia anual OLS + HAC/Newey–West rezago 1 + Wald + Holm sobre [P, T, SM, ET] + sensibilidad con rezagos 2 y 3, y análisis conjunto exploratorio con anomalías z sin estación ni tendencia y Pearson P–SM, T–SM, P–ET. Úsala siempre que haya que analizar, calcular, verificar, programar o explicar tendencias, significancia, p-valores, Holm, HAC, anomalías o correlaciones de precipitación, temperatura, humedad del suelo o evapotranspiración; cuando aparezca un CSV o datos de GPCP, MERRA-2 o GLDAS; al revisar down_to_earth.py u otro código estadístico del backend; o al redactar o revisar textos de resultados de la demo, aunque no se nombre la skill. Para estas cuatro variables tiene prioridad sobre motor-tendencias.
---

# Análisis Down to Earth: cuatro variables, dos análisis, un método

## Qué hace y por qué el método no se elige

Down to Earth cuenta cómo cambia la lluvia de una región y qué pasa a la vez con el calor, el agua del suelo y la
evapotranspiración. Hay **dos análisis**:

1. **Cada variable por separado** → ¿hay un cambio detectable? (tendencia con incertidumbre y corrección por
   comparaciones múltiples).
2. **Las cuatro juntas** → ¿coinciden sus variaciones mes a mes? (descriptivo; no demuestra causas).

El procedimiento está decidido de antemano y se aplica siempre igual. No se compara entre tests, no se elige el
rezago "que da mejor p" ni el par con mayor r: si el método se ajustara a los datos, el p-valor dejaría de
significar lo que dice. Esa es la razón de casi todas las reglas de abajo.

## Flujo

### 1. Identifica la entrada

| Lo que llega | Qué hacer |
|---|---|
| CSV mensual regional en unidades finales (mm/mes, °C, m³/m³, mm/mes) | Paso 2 directamente |
| CSV con las unidades de NASA (mm/día, K, kg/m², kg/m²/s) o nombres de campo (`sat_gauge_precip`, `T2M`…) | Paso 2 con `--unidades originales` |
| Cubos NetCDF / rejillas | Primero el promedio regional ponderado por área dentro del polígono ([references/datos.md](references/datos.md) §Promedio regional); luego el CSV mensual |
| Código a revisar (backend, notebook) | Sección "Revisar código" + [references/metodo.md](references/metodo.md) |
| Texto de resultados de la demo | [references/comunicacion.md](references/comunicacion.md) |

Si no está claro en qué unidades viene una columna, mira las magnitudes (T ≈ 290 → K; SM ≈ 20 → kg/m²; ET ≈ 1e-5
→ kg/m²/s) y dilo. Convertir dos veces o ninguna es el error de unidades más común.

### 2. Ejecuta el script (no reimplementes el método a mano)

```bash
# desde backend/ (usa el Python del proyecto: .venv/Scripts/python.exe en Windows, .venv/bin/python en Unix, o `uv run python`)
python .claude/skills/analisis-down-to-earth/scripts/analisis_dte.py ENTRADA.csv --salida DIR \
       [--unidades originales] [--region "Nombre real"] [--simulado] [--inicio 2001-01 --fin 2024-12]
python .claude/skills/analisis-down-to-earth/scripts/analisis_dte.py --autoprueba
```

El script aplica todo el método de [references/metodo.md](references/metodo.md) y escribe en `DIR`:
`resultados.json` (esquema fijo), `mensual.csv`, `anual.csv`, `resumen.md` y `graficos/` (serie anual con su recta
por variable y anomalías z con referencia 0, en SVG; también PNG si hay matplotlib). Usa statsmodels si está
instalado y, si no, numpy con las mismas fórmulas. Si dudas del entorno, corre antes `--autoprueba`.

Reimplementar a mano parece rápido, pero es donde se cuelan `fillna(0)`, la suma de temperaturas o el p×10. Si el
usuario quiere el código dentro del backend, usa el script como especificación ejecutable y compara resultados.

- `--region`: solo si el usuario la nombró. No inventes el nombre de la región.
- `--simulado`: si los datos son de prueba. Rotula todas las salidas.

### 3. Revisa antes de comunicar

El script no decide por ti si el resultado es creíble. Revisa:

- **Advertencias** de `metadata.advertencias`: relleno, ceros exactos, unidades sospechosas, duplicados, fracción
  de área que cambia con el tiempo.
- **Tramo usado** (`metadata.tramo_tendencias`) y **n de años**. Si es menor que el período pedido, explica qué
  años faltan y por qué. Con menos de 10 años la inferencia HAC es frágil: dilo.
- **Gráficos y residuos** (`quality.residuos`): un año atípico, un salto o una curva no los arregla HAC. Si los ves,
  menciónalos junto al resultado en vez de esconderlos.
- **Sensibilidad** (`sensibilidad`): si la decisión cambia con los rezagos 2 o 3, la etiqueta ya lleva "resultado
  sensible al rezago". El rezago 1 sigue siendo el principal.

### 4. Comunica con las reglas

Lee [references/comunicacion.md](references/comunicacion.md) antes de escribir texto para la demo. Lo esencial:

- La etiqueta la manda el **p ajustado por Holm**: ≤ 0.05 → "aumento/disminución con evidencia estadística según
  este método"; > 0.05 → "evidencia insuficiente" (que **no** significa "no cambió"). "Tras el ajuste" solo si el p
  sin ajustar era ≤ 0.05.
- Plantilla: "[Variable] cambió aproximadamente [valor y unidad] por década; IC95 % [inf, sup]; p ajustado [valor];
  [etiqueta]. Período [fechas], [n] años válidos."
- Relaciones: "P y SM mostraron asociación mensual r = [valor], con [n] meses, tras quitar estación y tendencia."
  Sin p y sin la palabra "significativo".
- Nada de causas ("el calor causó la sequía"), ni clasificar sequías o inundaciones, ni P − ET como balance cerrado.
- Incluye los resultados no concluyentes y los límites; rotula los datos simulados y los ejemplos ilustrativos.

## Reglas del método (resumen; detalle en metodo.md)

- **Faltante = faltante.** Nunca 0 ni interpolado: un cero inventado en lluvia es un mes de sequía que no ocurrió.
- **Unir por año y mes**, nunca por posición de fila: un mes ausente desplaza todo lo que viene después.
- **Anual**: P y ET se suman (12 meses); T y SM se promedian ponderando por días. Sumar temperaturas no tiene
  sentido físico. Un mes faltante deja el año incompleto: un total con 11 meses parecería un año seco.
- **Tramo común** más largo de años completos y consecutivos, el mismo para las cuatro variables. No se comprimen
  huecos, porque eso falsearía el eje de tiempo.
- **Tendencia**: OLS con constante, t = año − año inicial; HAC Bartlett con `maxlags=1` y `use_correction=True`,
  `use_t=False`; Wald normal bilateral; α = 0.05 fijado antes de ver datos.
- **Por década**: b y los dos límites del IC × 10. **El p nunca se multiplica**: no depende de la unidad de tiempo.
- **Holm sobre la familia fija [P, T, SM, ET]**, aunque en pantalla se oculten variables: la familia la define la
  pregunta, no lo que se muestra. Si una variable no se puede evaluar, se publica null con su motivo y entra a Holm
  con p = 1 interno (no publicado).
- **Sensibilidad**: rezagos 2 y 3 con Holm completo; informar, no escoger.
- **Conjunto**: anomalías z por mes calendario (2001–2024), quitar la tendencia lineal de cada z en tiempo real y
  Pearson **solo** para P–SM, T–SM y P–ET en el mismo mes. Sin retrasos, sin escoger el mayor r. El gráfico z
  conserva las tendencias; las correlaciones las eliminan: rotúlalo.

## Revisar código

Busca estos errores típicos y propone la corrección concreta (con el porqué):

| Error | Por qué está mal | Corrección |
|---|---|---|
| `fillna(0)`, `interpolate()`, `ffill` en datos | inventa meses secos o suaviza | dejar NaN; año incompleto |
| `.sum()` anual de T o SM, o media simple sin días | sin sentido físico / pesa igual febrero que enero | media ponderada Σ(X·días)/Σ(días) |
| media anual de P o ET en vez de suma | cambia la unidad (mm/mes ≠ mm/año) | suma de 12 meses |
| días fijos (30) o `× 86400` sin días del mes | error de hasta 10 % y bisiestos | `calendar.monthrange` |
| unir con `concat(axis=1)` / `zip` por posición | desalinea meses | merge por año-mes |
| `maxlags` ≠ 1 como principal, o elegir el rezago con menor p | método decidido de antemano | principal 1; 2 y 3 solo sensibilidad |
| t en meses mezclado con ×10, o `p * 10` | p no escala con el tiempo | ×10 a b e IC; p intacto |
| Bonferroni, o corrección sobre las variables visibles | familia mal definida | Holm sobre [P, T, SM, ET] siempre |
| etiqueta por p sin ajustar o por IC individual | ignora la multiplicidad | etiqueta por p de Holm |
| "sin cambio", "no cambió", "estable" con p > 0.05 | ausencia de evidencia ≠ evidencia de ausencia | "evidencia insuficiente" |
| "significativo"/p-valor en correlaciones, pares extra o retrasos | exploratorio; búsqueda de patrones | r y n de los 3 pares fijos |
| correlación sobre valores crudos o z sin quitar tendencia | la estación/tendencia común infla r | anomalías z sin tendencia |
| `cos(lat)` sin fracción de celda dentro del polígono | pesa igual celdas medio fuera | Aᵢ = área de la celda dentro del territorio |
| ET usada como PET, P − ET como balance, frases causales | límites físicos | ver datos.md y comunicacion.md |

Entrega la lista de problemas con línea y gravedad, y una versión corregida si el usuario la pide. Para verificar
la corrección, compara con la salida del script sobre el mismo CSV.

## Datos reales de NASA: `nasa-project dte`

El backend implementa este mismo método en `backend/src/core/motor/down_to_earth.py`
(`tramo_comun_anios_completos`, `ajustar_ols_hac_anual`, `evaluar_cuatro_tendencias_holm`,
`correlacion_exploratoria_sin_tendencia`, `analizar_cuatro_variables_dte`). El promedio regional usa el área
esférica de cada celda dentro de la región y la huella terrestre de GLDAS para las tres fuentes
(`motor/series.py: pesos_area_region`, `fraccion_tierra_desde_malla`). `tests/test_dte_paridad.py` comprueba que
backend y script dan los mismos números; si cambias uno, cambia el otro y vuelve a correr ese test.

Para analizar una región con datos reales (desde `backend/`):

```bash
# 1. Descarga OPeNDAP (GPCP v3.3, MERRA-2 T2M, GLDAS Noah 2.1) + análisis → resultados.json, mensual.csv,
#    anual.csv y serie_regional.csv. Lee EARTHDATA_USERNAME/PASSWORD de backend/.env. Nunca usa datos sintéticos.
PYTHONPATH=src .venv/Scripts/python.exe -m core.main dte --region <id de regiones.yaml> --salida resultados/dte/<id>
#    (o --bbox OESTE SUR ESTE NORTE). En Docker: docker compose --env-file backend/.env run --rm \
#    -v ./resultados:/app/resultados api nasa-project dte --region <id> --salida /app/resultados/dte/<id>
# 2. Resumen y gráficos con el script de la skill (y comprobación cruzada de cifras):
python .claude/skills/analisis-down-to-earth/scripts/analisis_dte.py resultados/dte/<id>/serie_regional.csv \
       --salida resultados/dte/<id>/skill --region "<nombre de la región>"
```

Salidas del comando: `resultados.json` (incluye `data_cleaning` con resumen y registro), `serie_regional.csv`
(precisión completa), `mensual.csv` y `anual.csv` con formato (decimales fijos, unidades en el nombre de columna,
vacío = faltante, marcas de completitud y de tramo), `registro_limpieza.csv` y `diccionario_datos.csv`. Para
reanalizar sin descargar: `... -m core.main dte --region <id> --desde-csv resultados/dte/<id>/serie_regional.csv
--salida resultados/dte/<id>`.

Las pendientes, p de Holm y r de `resultados.json` deben coincidir con las de `skill/resultados.json`. Revisa
siempre `metadata.warnings`, `metadata.trend_span`, `data_cleaning.summary` y `quality.area_coverage_*` antes de
comunicar.

Endpoints de la API con este mismo método (`backend/src/core/api/rutas/down_to_earth.py`, esquema `ResultadoDTE`):

- `POST /api/v1/down-to-earth/calcular` (serie mensual en JSON) y `/calcular/csv` (archivo): cálculo exacto y
  síncrono sobre datos que envía el cliente, en unidades finales u originales NASA.
- `POST /api/v1/down-to-earth/trabajos` → `GET .../trabajos/{id}` → `.../resultado` y `.../tablas/{tabla}`:
  descarga real por OPeNDAP y análisis en segundo plano (minutos), sin datos sintéticos.
- `GET /api/v1/down-to-earth/analisis`: rellena con datos sintéticos lo que no está en caché salvo que se pida
  `estricto_memoria=true`; en ese caso `metadata.simulated` es `true`. Un resultado con `simulated: true` nunca se
  presenta como dato real.

`tests/test_api_dte_calculo.py` comprueba por API que `/calcular` da los mismos números que el script.

La skill `motor-tendencias` (n efectivo + Mann-Kendall, veredicto "significativo/indicio") sirve para el escáner
"dos caras", **no** para estas cuatro variables: no mezcles sus etiquetas con las de aquí.

## Datos simulados y ejemplos

Los ejemplos de las guías son ilustrativos y los datos de prueba son simulados. Rotúlalos siempre así, también en
gráficos y JSON (`--simulado`). No inventes cifras ni el nombre de una región: si falta un dato, di que falta.

## Referencias

- [references/datos.md](references/datos.md): productos, campos, conversiones con controles, período, límites
  físicos, valores de relleno y promedio regional por área.
- [references/metodo.md](references/metodo.md): preparación, fórmulas, Holm, sensibilidad, análisis conjunto y
  esquema JSON de salida.
- [references/comunicacion.md](references/comunicacion.md): etiquetas, plantillas, definiciones correctas y frases
  prohibidas.
