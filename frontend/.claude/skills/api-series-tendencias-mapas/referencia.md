# Referencia — Schemas y outputs reales de `/api/v1/series`, `tendencias`, `indicadores`, `escaner`, `dos-caras` y `mapas`

## 1. `GET /api/v1/series/{variable_id}` (`SerieRespuestaDTO`)

Parámetros query: `region`, `oeste`, `sur`, `este`, `norte`, `inicio` (`AAAA-MM`), `fin` (`AAAA-MM`), `anual` (`"suma" | "media" | "media_ponderada_dias"`), `unidad` (`"mm/dia" | "mm/mes"`), `mascara` (`"tierra"`), `descargar`, `sintetico`.

### Output real (`GET /api/v1/series/lluvia_gpcp?region=noreste_mexico&inicio=2001-01&fin=2024-12&sintetico=true`)
```json
{
  "variable": "lluvia_gpcp",
  "nombre_simple": "Precipitación (P)",
  "definicion_simple": "Cuánta lluvia cayó en el mes, combinando satélites y pluviómetros.",
  "grupo": "lluvia",
  "dataset": "GPCP Precipitation Level 3 Monthly 0.5-Degree V3.3",
  "short_name": "GPCPMON",
  "unidad": "mm/mes",
  "frecuencia_serie": "mensual",
  "region": {
    "id": "noreste_mexico",
    "nombre": "Noreste de México",
    "bbox": [-106.0, 22.0, -97.0, 30.0]
  },
  "periodo": ["2001-01", "2024-12"],
  "media_climatologia": 76.22093315722896,
  "climatologia_mensual": [
    { "mes": 1, "valor": 41.66334597710314 },
    { "mes": 2, "valor": 48.10219401238412 }
  ],
  "calidad": {
    "aceptada": true,
    "n_esperados": 288,
    "n_faltantes": 0,
    "fraccion_faltante": 0.0,
    "motivo": null,
    "meses_poca_cobertura": null
  },
  "puntos": [
    {
      "fecha": "2001-01",
      "t": 0.0,
      "valor": 52.372515426536985,
      "anomalia": 10.709169449433844
    }
  ],
  "fuente_datos": "sintetico"
}
```
> Si se solicita `?anual=suma`, `frecuencia_serie` pasa a `"anual"`, `climatologia_mensual` es `null` y cada punto tiene `"fecha": "2001"`, `"t": 2001.0`, `"anomalia": null`.

---

## 2. `GET /api/v1/tendencias/{variable_id}` (`TendenciaRespuestaDTO`)

Parámetros adicionales: `alfa` (`0.05`), `incluir_serie` (`true`).

### Output real (`GET /api/v1/tendencias/lluvia_gpcp?region=noreste_mexico&sintetico=true`)
```json
{
  "tendencia": {
    "variable": "lluvia_gpcp",
    "region": "noreste_mexico",
    "periodo": ["2001-01", "2024-12"],
    "n": 288,
    "r1": 0.07950082446400268,
    "n_ef": 245.57995375871752,
    "pendiente_ols_decada": -6.920378244476355,
    "ic95_decada": [-7.810261173994715, -6.030495314957993],
    "p_t": 1.5042624902701452e-37,
    "sen_decada": -7.042411592871291,
    "mk_z": -11.094699037519721,
    "mk_tau": -0.5072590011614402,
    "p_mk": 0.0,
    "cambio_pct_decada": -9.079366989906777,
    "snr": -1.0092937220766696,
    "n_star_anios": 8.611253034649417,
    "anios_faltantes": 0.0,
    "veredicto": "significativo",
    "direccion": "baja",
    "metodos": ["ols_neff", "mk_hamed_rao"]
  },
  "metadatos": {
    "nombre_simple": "Precipitación (P)",
    "definicion_simple": "Cuánta lluvia cayó en el mes, combinando satélites y pluviómetros.",
    "grupo": "lluvia",
    "dataset": "GPCP Precipitation Level 3 Monthly 0.5-Degree V3.3",
    "short_name": "GPCPMON",
    "unidad": "mm/mes",
    "unidad_pendiente": "mm/mes/decada",
    "frecuencia_serie": "mensual",
    "media_climatologia": 76.22093315722896,
    "recta_ols": {
      "beta0": 8.275618984019642,
      "beta1_por_paso": -0.05766981870396962
    },
    "calidad": {
      "aceptada": true,
      "n_esperados": 288,
      "n_faltantes": 0,
      "fraccion_faltante": 0.0,
      "motivo": null
    },
    "fuente_datos": "sintetico"
  },
  "puntos": [
    {
      "fecha": "2001-01",
      "t": 0.0,
      "valor": 52.372515426536985,
      "anomalia": 10.709169449433844
    }
  ],
  "climatologia_mensual": [
    { "mes": 1, "valor": 41.66334597710314 }
  ]
}
```

---

## 3. `GET /api/v1/indicadores`

Calcula los 5 indicadores anuales ETCCDI a partir de GPM IMERG diario (`lluvia_imerg_dia`) y evalúa `dos_caras_extremos` (`cdd_imerg` vs `r20mm_imerg`).

### Output real (`GET /api/v1/indicadores?region=noreste_mexico&sintetico=true`)
```json
{
  "region": { "id": "noreste_mexico", "nombre": "Noreste de México", "bbox": [-106.0, 22.0, -97.0, 30.0] },
  "periodo": ["2001", "2024"],
  "cortar_en_anio": true,
  "fuente_datos": "sintetico",
  "indicadores": {
    "cdd_imerg": {
      "id": "cdd_imerg",
      "indicador": "cdd",
      "nombre_simple": "Racha seca más larga",
      "definicion_simple": "El mayor número de días seguidos sin lluvia útil (menos de 1 mm) en un año.",
      "unidad": "dias",
      "serie": [
        { "anio": 2001, "valor": 102.17713989264698 }
      ],
      "tendencia": {
        "variable": "cdd_imerg",
        "pendiente_ols_decada": 6.362331325299388,
        "veredicto": "significativo",
        "direccion": "sube"
      }
    },
    "r20mm_imerg": { "id": "r20mm_imerg", "indicador": "r20mm", "unidad": "dias" },
    "dias_humedos_imerg": { "id": "dias_humedos_imerg", "indicador": "dias_humedos", "unidad": "dias" },
    "prcptot_imerg": { "id": "prcptot_imerg", "indicador": "prcptot", "unidad": "mm/anio" },
    "sdii_imerg": { "id": "sdii_imerg", "indicador": "sdii", "unidad": "mm/dia" }
  },
  "dos_caras_extremos": {
    "region_a": { "variable": "cdd_imerg", "veredicto": "significativo", "direccion": "sube" },
    "region_b": { "variable": "r20mm_imerg", "veredicto": "significativo", "direccion": "baja" },
    "signo_opuesto": true,
    "ambas_significativas": true,
    "dos_caras": true
  }
}
```

---

## 4. `GET /api/v1/escaner` y `POST /api/v1/escaner`

Body de `POST /api/v1/escaner` (`PeticionEscanerDTO`):
```json
{
  "region": "noreste_mexico",
  "bbox": null,
  "inicio": "2001-01",
  "fin": "2024-12",
  "variables": ["lluvia_gpcp", "temp_aire", "humedad_suelo", "cdd_imerg", "r20mm_imerg"],
  "grupo": null,
  "fuente": null,
  "alfa": 0.05,
  "descargar": false,
  "sintetico": true
}
```

### Output real (`200 OK`)
```json
{
  "region": { "id": "noreste_mexico", "nombre": "Noreste de México", "bbox": [-106.0, 22.0, -97.0, 30.0] },
  "periodo": ["2001-01", "2024-12"],
  "fuente_datos": "sintetico",
  "resultados": [
    {
      "variable": "sdii_imerg",
      "region": "noreste_mexico",
      "periodo": ["2001", "2024"],
      "n": 24,
      "r1": 0.17921120344367686,
      "n_ef": 16.70517635842038,
      "pendiente_ols_decada": -2.0976929834209876,
      "ic95_decada": [-2.2910632157402864, -1.9043227511016888],
      "p_t": 5.548155074722e-13,
      "sen_decada": -2.073226922371679,
      "mk_z": -6.374731572788186,
      "mk_tau": -0.9347826086956522,
      "p_mk": 1.8328361051089814e-10,
      "cambio_pct_decada": -22.432717466145803,
      "snr": -1.3952218070740403,
      "n_star_anios": null,
      "anios_faltantes": null,
      "veredicto": "significativo",
      "direccion": "baja",
      "metodos": ["ols_neff", "mk_hamed_rao", "serie_anual"],
      "nombre_simple": "Fuerza de la lluvia",
      "definicion_simple": "Cuánto llueve, en promedio, en un día con lluvia.",
      "grupo": "calculada",
      "dataset": "calculada a partir de GPM IMERG diario",
      "unidad": "mm/dia"
    }
  ],
  "rechazadas": []
}
```

---

## 5. `GET /api/v1/dos-caras` y `POST /api/v1/dos-caras`

Body de `POST /api/v1/dos-caras` (`PeticionDosCarasDTO`):
```json
{
  "variable": "r20mm_imerg",
  "region_a": "noreste_mexico",
  "bbox_a": null,
  "region_b": "noreste_mexico",
  "bbox_b": null,
  "variable_b": "cdd_imerg",
  "inicio": "2001-01",
  "fin": "2024-12",
  "alfa": 0.05,
  "descargar": false,
  "sintetico": true
}
```

### Estructura de respuesta (`200 OK`)
- `region_a`: objeto `TendenciaMotorDTO` (20 claves) del primer lado.
- `region_b`: objeto `TendenciaMotorDTO` (20 claves) del segundo lado.
- `signo_opuesto`: `boolean`.
- `ambas_significativas`: `boolean`.
- `dos_caras`: `boolean` (`signo_opuesto && ambas_significativas`).
- `detalle_a`: `TendenciaRespuestaDTO` completo (con `metadatos`, `puntos` y `climatologia_mensual`).
- `detalle_b`: `TendenciaRespuestaDTO` completo.

---

## 6. `GET /api/v1/mapas/{variable_id}`

### Output real (`GET /api/v1/mapas/lluvia_gpcp?region=noreste_mexico&sintetico=true`)
```json
{
  "variable": "lluvia_gpcp",
  "nombre_simple": "Precipitación (P)",
  "unidad_pendiente": "mm/mes/decada",
  "region": { "id": "noreste_mexico", "bbox": [-106.0, 22.0, -97.0, 30.0] },
  "periodo": ["2001-01", "2024-12"],
  "alfa": 0.05,
  "fuente_datos": "sintetico",
  "codigos_veredicto": {
    "2": "significativo",
    "1": "indicio",
    "0": "sin tendencia clara"
  },
  "lat": [22.25, 24.75, 27.25, 29.75],
  "lon": [-105.75, -102.9167, -100.0833, -97.25],
  "pendiente_decada": [
    [-7.0582, -7.2311, -7.404, -7.5769],
    [-6.6431, -6.816, -6.9889, -7.1618],
    [-6.228, -6.4009, -6.5738, -6.7467],
    [-5.8129, -5.9858, -6.1587, -6.3316]
  ],
  "p_t": [
    [6.2e-09, 3.1e-09, 1.5e-09, 7.8e-10]
  ],
  "p_mk": [
    [8.1e-08, 4.2e-08, 2.1e-08, 1.1e-08]
  ],
  "veredicto": [
    [2.0, 2.0, 2.0, 2.0],
    [2.0, 2.0, 2.0, 2.0],
    [2.0, 2.0, 2.0, 2.0],
    [2.0, 2.0, 2.0, 2.0]
  ],
  "resumen": {
    "n_pixeles_total": 16,
    "n_pixeles_validos": 16,
    "n_significativos_secos": 16,
    "n_significativos_humedos": 0,
    "n_indicio": 0
  }
}
```

