# Referencia — Schemas y outputs reales de Down to Earth (`/catalog`, `/demo/result`, `/demo/csv`)

## 1. Parámetros de consulta de `GET /demo/result`

| Parámetro | Tipo | Default | Descripción |
|---|---|---|---|
| `region` | `string` | `"sahel"` | ID de región predefinida (ej. `"corredor_seco_centroamericano"`, `"noreste_mexico"`) o slug personalizado si se envía bbox |
| `oeste` | `number` | `null` | Longitud mínima `[-180, 180]` (requiere `sur`, `este`, `norte`) |
| `sur` | `number` | `null` | Latitud mínima `[-90, 90]` |
| `este` | `number` | `null` | Longitud máxima `[-180, 180]` |
| `norte` | `number` | `null` | Latitud máxima `[-90, 90]` |
| `inicio` | `string` | `"2001-01"` | Mes inicial en formato `AAAA-MM` |
| `fin` | `string` | `"2024-12"` | Mes final en formato `AAAA-MM` |
| `alfa` | `number` | `0.05` | Nivel de significancia familiar para el procedimiento de Holm `(0, 0.5)` |
| `mascara` | `"tierra"` | `null` | Si se envía `"tierra"`, descarta celdas marinas antes de promediar |
| `descargar` | `boolean` | `false` | Si `true`, consulta OPeNDAP de NASA en vivo cuando el cubo no está en RAM |
| `sintetico` | `boolean` | `false` | Si `true`, fuerza el generador sintético determinista |
| `estricto_memoria` | `boolean` | `false` | Si `true` y no está en RAM ni se pidió `descargar=true`, devuelve `404` en lugar de fallback sintético |

---

## 2. Output real de `GET /demo/result?region=corredor_seco_centroamericano&sintetico=true` (`200 OK`)

> Output completo disponible en `docs/api/ejemplos/demo_result.json`.

```json
{
  "metadata": {
    "project": "Down to Earth — Cuatro variables, dos formas de analizarlas",
    "region": {
      "id": "corredor_seco_centroamericano",
      "nombre": "Corredor Seco Centroamericano",
      "descripcion": "Vertiente pacífica de Guatemala, El Salvador, Honduras y Nicaragua (alta vulnerabilidad agrícola a sequías y El Niño).",
      "zona": "centroamerica",
      "pais": "Guatemala / El Salvador / Honduras / Nicaragua",
      "es_latinoamerica": true,
      "bbox": [-91.0, 12.0, -85.0, 16.0],
      "predefinida": true,
      "coordenadas": {
        "oeste": -91.0,
        "sur": 12.0,
        "este": -85.0,
        "norte": 16.0,
        "centro": { "lat": 14.0, "lon": -88.0 }
      }
    },
    "period": ["2001-01", "2024-12"],
    "months_total": 288,
    "years_expected": 24,
    "years_complete_count": 24,
    "trend_span": {
      "start": 2001,
      "end": 2024,
      "n_years": 24,
      "criterion": "tramo común más largo de años completos y consecutivos (empate → el más reciente)"
    },
    "simulated": true,
    "warnings": ["DATOS SIMULADOS: al menos una variable es sintética; las cifras no describen la región real."],
    "spatial_weighting": "área esférica de cada celda dentro de la región × fracción de tierra según la huella de GLDAS",
    "alpha": 0.05,
    "method": {
      "ols_formula": "y = a + b * t, donde t = anio - anio_inicial",
      "cov_type": "HAC",
      "cov_kwds": {
        "maxlags": 1,
        "kernel": "bartlett",
        "use_correction": true
      },
      "use_t": false,
      "multiple_testing": "holm",
      "family": ["P", "T", "SM", "ET"],
      "sensitivity_lags": [1, 2, 3]
    },
    "source": "sintetico",
    "almacenamiento_disco": false
  },
  "variables": {
    "P": {
      "id": "lluvia_gpcp",
      "code": "P",
      "name": "Precipitación (P)",
      "question": "¿Está llegando más o menos agua?",
      "why_chosen": "Es el fenómeno principal del proyecto.",
      "collection": "GPCP mensual v3.3 (la v3.2 termina en 2023-12; v3.3 conserva sat_gauge_precip)",
      "short_name": "GPCPMON",
      "field": "sat_gauge_precip",
      "conversion_rule": "mm/día × días del mes → mm/mes",
      "annual_aggregation": "suma",
      "units": {
        "monthly": "mm/mes",
        "annual": "mm/anio",
        "slope_decade": "mm por década (total anual)"
      },
      "monthly": [
        { "date": "2001-01", "value": 59.27356607791693, "z": 0.08093895645297859 }
      ],
      "annual": [
        { "year": 2001, "value": 1039.4318316704096, "fitted": 1036.4094619419488 }
      ],
      "intercept_a": 1036.4094619419488,
      "slope_annual": 8.192705328909682,
      "se_annual": 0.45769725242799375,
      "z_stat": 17.899835066627546,
      "slope_decade": 81.92705328909682,
      "ci95": [72.95635198327876, 90.89775459491488],
      "p_raw": 1.1827165717997752e-71,
      "p_holm": 1.1827165717997752e-71,
      "significant": true,
      "direction": "aumento",
      "estimate_sign": "positiva",
      "label": "aumento con evidencia estadística según este método",
      "summary_text": "Precipitación (P) cambió aproximadamente +81.9 mm por década (total anual); IC95 % [+73.0, +90.9]; p ajustado < 0.001; aumento con evidencia estadística según este método. Período 2001–2024, 24 años válidos.",
      "sensible_al_rezago": false,
      "sensitivity": {
        "lag_1": {
          "maxlags": 1,
          "se_annual": 0.45769725242799375,
          "z_stat": 17.899835066627546,
          "ci95": [72.95635198327876, 90.89775459491488],
          "p_raw": 1.1827165717997752e-71,
          "p_holm": 1.1827165717997752e-71,
          "significant": true
        },
        "lag_2": { "maxlags": 2, "significant": true },
        "lag_3": { "maxlags": 3, "significant": true }
      },
      "quality": {
        "n_exact_zeros": 0,
        "n_months_expected": 288,
        "n_months_valid": 288,
        "n_months_missing": 0,
        "missing_fraction_monthly": 0.0,
        "n_years_expected": 24,
        "n_years_complete": 24,
        "complete_period": true,
        "area_coverage_mean": 1.0,
        "area_coverage_min": 1.0,
        "area_coverage_stable": true,
        "warnings": []
      }
    },
    "T": { "id": "temp_aire", "code": "T", "units": { "monthly": "°C", "annual": "°C", "slope_decade": "°C por década" } },
    "SM": { "id": "humedad_suelo", "code": "SM", "units": { "monthly": "m³/m³", "annual": "m³/m³", "slope_decade": "m³/m³ por década" } },
    "ET": { "id": "evapotranspiracion", "code": "ET", "units": { "monthly": "mm/mes", "annual": "mm/anio", "slope_decade": "mm por década (total anual)" } }
  },
  "joint": {
    "preprocessing": {
      "seasonal_removal": "Promedio μ_mes y desviación estándar s_mes calculados por mes calendario (enero..diciembre) en todo el período elegido.",
      "standardization": "z = (valor - μ_mes) / s_mes (escala adimensional comparable entre P, T, SM y ET).",
      "detrending_for_correlation": "Para las correlaciones r se elimina por regresión OLS la tendencia lineal de cada serie de anomalías z.",
      "note": "Estas correlaciones son exploratorias: no se les asigna p-valor ni etiqueta de significancia estadística."
    },
    "standardized_anomalies": [
      {
        "date": "2001-01",
        "P": 0.08093895645297859,
        "T": -1.7104975038767158,
        "SM": -0.5771133502445402,
        "ET": -0.5942556643857371
      }
    ],
    "pairs": {
      "P-SM": {
        "pair": "P-SM",
        "var_x": "P",
        "var_y": "SM",
        "question": "¿Meses con menos lluvia también tienen el suelo más seco?",
        "interpretation_note": "El suelo puede responder con retraso; la correlación del mismo mes no captura toda la memoria hídrica.",
        "r": 0.8559675161252982,
        "n": 288,
        "common_period": ["2001-01", "2024-12"],
        "direction_description": "variación conjunta en el mismo sentido",
        "summary_text": "P y SM mostraron asociación mensual r = +0.86, con 288 meses, tras quitar la estacionalidad y la tendencia lineal."
      },
      "T-SM": { "pair": "T-SM", "var_x": "T", "var_y": "SM", "r": -0.7716038792866792, "n": 288 },
      "P-ET": { "pair": "P-ET", "var_x": "P", "var_y": "ET", "r": 0.8069011305478856, "n": 288 }
    },
    "pairs_list": [
      { "pair": "P-SM", "var_x": "P", "var_y": "SM", "r": 0.8559675161252982, "n": 288 }
    ]
  },
  "conclusion": {
    "joint_reading": "En el período analizado, con evidencia estadística tras el ajuste de Holm, aumentó la precipitación, aumentó la temperatura del aire, aumentó la humedad superficial del suelo y aumentó la evapotranspiración real.",
    "changes_with_statistical_evidence": [
      "Precipitación (P) cambió aproximadamente +81.9 mm por década; IC95 % [+73.0, +90.9]; p ajustado = 1.2e-71."
    ],
    "inconclusive_or_insufficient_evidence": [],
    "exploratory_associations": [
      "P y SM mostraron asociación mensual r = +0.86, con 288 meses, tras quitar la estacionalidad y la tendencia lineal."
    ],
    "methodological_limits": [
      "La coincidencia temporal o correlación entre P, T, SM y ET describe relación entre variables, no prueba causalidad directa."
    ]
  }
}
```

---

### Valores posibles de `label`, `direction` y `estimate_sign`

| Caso | `label` | `direction` | `significant` |
|---|---|---|---|
| p_holm ≤ 0.05, pendiente > 0 | `aumento con evidencia estadística según este método` | `"aumento"` | `true` |
| p_holm ≤ 0.05, pendiente < 0 | `disminución con evidencia estadística según este método` | `"disminucion"` | `true` |
| p_holm > 0.05 y p_raw ≤ 0.05 | `evidencia insuficiente tras el ajuste` | `null` | `false` |
| p_holm > 0.05 y p_raw > 0.05 | `evidencia insuficiente` | `null` | `false` |
| SE cero o no finito | `sin inferencia: …` | `null` | `null` |
| sin años completos | `no evaluable: <motivo>` | `null` | `null` |

- Si la decisión cambia con los rezagos 2 o 3, `label` termina en `; resultado sensible al rezago`.
- `estimate_sign` (`positiva`/`negativa`/`nula`) es el signo de la pendiente estimada, también cuando no hay
  evidencia. Muéstralo como "estimación positiva/negativa", nunca como "aumentó/disminuyó".
- "Evidencia insuficiente" **no** significa "sin cambio": el front no debe mostrar "sin cambio" ni "estable".
- Si `metadata.simulated` es `true`, rotula toda la vista como **datos simulados**.
- Las cuatro pendientes usan el mismo tramo `metadata.trend_span`; muéstralo junto a los resultados.
- `data_cleaning`: `steps` (reglas de limpieza), `summary[P|T|SM|ET]` (conteos: `relleno`, `fuera_de_rango`,
  `no_finitos`, `duplicados_*`, `meses_ausentes`, `ceros_exactos`, `n_meses_validos`, `anios_incompletos`) y `log`
  (`[{fecha, variable, valor_original, accion, motivo}]`). Útil para una vista de "calidad de datos".

---

## 3. Output real de `GET /catalog` (`200 OK`)

> Output completo disponible en `docs/api/ejemplos/catalog_dte.json`.

Devuelve:
- `project`: título del estudio
- `period_default`: `["2001-01", "2024-12"]`
- `months_expected`: `288`, `years_expected`: `24`
- `collections`: las 3 colecciones (`GPCPMON`, `M2TMNXSLV`, `GLDAS_NOAH025_M`)
- `variables`: las 4 variables (`P`, `T`, `SM`, `ET`) con `question`, `why_chosen`, `conversion_rule` y `units`
- `method`: descripción textual de OLS + HAC + Wald + Holm + Pearson sobre `z`
- `regions`: las 23 regiones predefinidas con `coordenadas`, `mallas_reales` y `shortcut`

---

## 4. Output real de `GET /demo/csv/anual` y `GET /demo/csv/mensual`

### `GET /demo/csv/anual?region=corredor_seco_centroamericano&sintetico=true`
```csv
anio,P_mm_anio,T_degC,SM_m3_m3,ET_mm_anio
2001,1039.43,24.0086,0.219401,549.653
2002,1045.98,24.0314,0.223429,549.422
2003,1057.48,24.105,0.226607,558.758
```

### `GET /demo/csv/mensual?region=corredor_seco_centroamericano&sintetico=true`
```csv
fecha,P_mm_mes,T_degC,SM_m3_m3,ET_mm_mes
2001-01,47.1214,19.3095,0.156267,23.6281
```


---

## 5. Endpoints de cálculo exacto (`/api/v1/down-to-earth/...`)

Todos usan el mismo motor que `/demo/result` (limpieza estructural + OLS anual + HAC rezago 1 + Holm sobre
[P, T, SM, ET] + sensibilidad rezagos 2 y 3 + anomalías z y Pearson P–SM, T–SM, P–ET) y devuelven `ResultadoDTE`.

### 5.1 `POST /calcular` — desde una serie mensual en JSON (síncrono)

```json
{
  "serie": [{ "fecha": "2001-01", "P": 15.9, "T": 15.5, "SM": 0.179, "ET": 27.4 }],
  "unidades": "finales",
  "inicio": "2001-01",
  "fin": "2024-12",
  "alfa": 0.05,
  "region": "corredor_seco_centroamericano",
  "simulado": false,
  "incluir_tablas": true
}
```

- `unidades`: `"finales"` (mm/mes, °C, m³/m³, mm/mes) u `"originales"` NASA (mm/día, K, kg/m², kg/m²/s).
- Valores `null` = faltante (nunca se rellenan). Variables ausentes → `label: "no evaluable: …"`.
- `incluir_tablas: true` añade `tablas.mensual`, `tablas.anual` y `tablas.diccionario` (registros con formato).
- Errores: `422` (cuerpo inválido), `400` (`parametro_invalido`: sin columna de fecha o de variables, período mal).

### 5.2 `POST /calcular/csv` — desde un archivo (multipart/form-data, síncrono)

Campos: `archivo` (CSV ≤ 5 MB), `unidades`, `inicio`, `fin`, `alfa`, `region`, `simulado`, `incluir_tablas`.
El CSV acepta `fecha`/`date`/`time` (o `anio`+`mes`) y columnas `P, T, SM, ET` o los campos NASA
`sat_gauge_precip, T2M, SoilMoi0_10cm_inst, Evap_tavg`. `metadata.input` informa las columnas usadas.

```ts
const fd = new FormData();
fd.append("archivo", file);
fd.append("unidades", "originales");
const res = await fetch(`${BACKEND_URL}/api/v1/down-to-earth/calcular/csv`, { method: "POST", body: fd });
```

### 5.3 Trabajos con datos reales de NASA (asíncrono)

1. `POST /trabajos` con `{"region": "corredor_seco_centroamericano", "inicio": "2001-01", "fin": "2024-12"}`
   (o `"bbox": [oeste, sur, este, norte]`) → `202` con `TrabajoDTE`.
2. Sondear `GET /trabajos/{id}` cada 5–10 s: `estado` (`pendiente|ejecutando|completado|error`), `etapa`
   (`P|T|SM|ET|analisis`), `paso_actual/total_pasos`, `porcentaje`, `mensaje`, `enlaces`.
3. Cuando `estado == "completado"`: `GET /trabajos/{id}/resultado` (`?incluir_tablas=true` opcional).
   Antes de terminar o si falló → `409`. Id inexistente → `404`.
4. Tablas: `GET /trabajos/{id}/tablas/{mensual|anual|limpieza|diccionario|serie_regional}?formato=csv|json`.

Una corrida completa (4 productos × 288 meses) tarda del orden de 30 min por región. Nunca usa datos sintéticos:
si falta un producto, el trabajo termina en `error`. Después, `GET /down-to-earth/analisis?region=…&estricto_memoria=true`
responde al instante con los cubos ya en RAM.

```ts
const t = await (await fetch(`${BACKEND_URL}/api/v1/down-to-earth/trabajos`, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ region: "corredor_seco_centroamericano" }),
})).json();
// sondear t.enlaces.estado hasta estado === "completado", luego:
const resultado = await (await fetch(`${BACKEND_URL}${t.enlaces.resultado}`)).json();
```
