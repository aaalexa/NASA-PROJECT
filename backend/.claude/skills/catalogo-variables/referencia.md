# Referencia — variables iniciales y unidades

## 1. Variables iniciales

| id | grupo | short_name | versión | variable (archivo) | unidad_original | conversion | unidad_final | frecuencia | desde | resolución |
|---|---|---|---|---|---|---|---|---|---|---|
| lluvia_gpcp | lluvia | GPCPMON | 3.3* | sat_gauge_precip | mm/dia | `{op: dias_del_mes}` | mm/mes | mensual | 1983-01 | 0.5° |
| lluvia_merra2 | lluvia | M2TMNXFLX | 5.12.4 | PRECTOTCORR | kg m-2 s-1 | `{op: factor, valor: 86400}` | mm/dia | mensual | 1980-01 | 0.5° × 0.625° |
| lluvia_imerg_mes | lluvia | GPM_3IMERGM | 07 | precipitation | mm/h | `{op: factor, valor: 24}` | mm/dia | mensual | 1998-01 | 0.1° |
| lluvia_imerg_dia | lluvia | GPM_3IMERGDF | 07 | precipitation | mm/dia | `{op: ninguna}` | mm/dia | diaria | 1998-01 | 0.1° |
| temp_aire | causa | M2TMNXSLV | 5.12.4 | T2M | K | `{op: suma, valor: -273.15}` | degC | mensual | 1980-01 | 0.5° × 0.625° |
| vapor_agua | causa | M2TMNXSLV | 5.12.4 | TQV | kg m-2 | `{op: ninguna}` | mm | mensual | 1980-01 | 0.5° × 0.625° |
| humedad_suelo | agua | GLDAS_NOAH025_M | 2.1 | SoilMoi0_10cm_inst | kg m-2 | `{op: ninguna}` | mm | mensual | 2000-01 | 0.25° |
| evaporacion | agua | GLDAS_NOAH025_M | 2.1 | Evap_tavg | kg m-2 s-1 | `{op: factor, valor: 86400}` | mm/dia | mensual | 2000-01 | 0.25° |
| escorrentia | agua | GLDAS_NOAH025_M | 2.1 | Qs_acc | kg m-2 3h-1 | `{op: factor, valor: 8}` | mm/dia | mensual | 2000-01 | 0.25° |
| ndvi | agua | MOD13C2 | 061 | CMG_0_05_Deg_Monthly_NDVI** | escalado | `{op: factor, valor: 0.0001}` | 1 | mensual | 2000-02 | 0.05° |
| cultivos | social | MCD12Q1 | 061 | LC_Type1 | clase IGBP | `{op: clases, valores: [12, 14]}` | booleano | anual | 2001 | 500 m |
| poblacion | social | CIESIN_SEDAC_GPWv4_POPCOUNT_R11 | 4.11 | Population Count*** | personas | `{op: ninguna}` | personas | anual (2000, 2005, 2010, 2015, 2020) | 2000 | 2.5′ / 15′ / 30′ |

\* El pedido original dice v3.2, pero v3.2 termina en 2023-12 (verificado en CMR el 2026-11-13); v3.3 cubre
1983-01 → 2025-12. Decide cuál usar y anótalo en `version`. Verifica que v3.3 mantenga el nombre `sat_gauge_precip`.
\** El nombre del producto es "CMG 0.05 Deg Monthly NDVI"; en AppEEARS la capa usa guiones bajos. Verifícalo con
`GET /product/MOD13C2.061`.
\*** El NetCDF de GPW tiene una variable con nombre largo y una dimensión `raster`; ver `nasa-acceso-datos/referencia.md` §4.

Notas de grupo: `ndvi` va en "agua" porque mide la respuesta de la vegetación al agua disponible; `cultivos` y
`poblacion` van en "social" porque sirven para medir a quién afecta. Cámbialo si el equipo lo decide, pero en
`catalogo.yaml`, no en el código.

### Variables calculadas (grupo `calculada`)

Los indicadores de la skill `indicadores-lluvia` se registran así, para que el escáner los trate como cualquier otra variable:

```yaml
  - id: cdd_imerg
    grupo: calculada
    nombre_simple: Racha seca más larga
    definicion_simple: El mayor número de días seguidos sin lluvia útil (menos de 1 mm) en un año.
    dataset: calculada a partir de GPM IMERG diario
    short_name: null
    variable: CDD
    origen: lluvia_imerg_dia
    indicador: CDD
    unidad_original: dias
    conversion: {op: ninguna}
    unidad_final: dias
    desde: "1998"
    resolucion: 0.1°
    frecuencia: anual
```

## 2. Unidades conocidas (`UNIDADES_CONOCIDAS`)

```python
UNIDADES_CONOCIDAS = {
    "mm/dia", "mm/mes", "mm/anio", "mm/h", "mm",
    "kg m-2 s-1", "kg m-2", "kg m-2 3h-1",
    "K", "degC",
    "1", "escalado", "clase IGBP", "booleano", "fraccion",
    "personas", "dias",
}
GRUPOS = {"lluvia", "causa", "agua", "social", "calculada"}
FRECUENCIAS = {"diaria", "mensual", "anual"}
OPERACIONES = {"ninguna", "factor", "suma", "dias_del_mes", "clases"}
```

Si añades una unidad, añádela aquí **y** escribe su test de conversión.

## 3. Valores de prueba (para `tests/test_catalogo.py`)

| id | entrada | salida esperada |
|---|---|---|
| lluvia_gpcp | 2.0 mm/dia, 2023-02 / 2024-02 / 2024-01 | 56.0 / 58.0 / 62.0 mm/mes |
| lluvia_merra2 | 1e-4 kg m-2 s-1 | 8.64 mm/dia |
| lluvia_imerg_mes | 0.5 mm/h | 12.0 mm/dia |
| lluvia_imerg_dia | 7.3 mm/dia | 7.3 mm/dia |
| temp_aire | 300.0 K | 26.85 degC |
| vapor_agua | 25.0 kg m-2 | 25.0 mm |
| humedad_suelo | 30.0 kg m-2 | 30.0 mm |
| evaporacion | 2e-5 kg m-2 s-1 | 1.728 mm/dia |
| escorrentia | 1.5 kg m-2 3h-1 | 12.0 mm/dia |
| ndvi | 5000 | 0.5 |
| cultivos | [10, 12, 14, 16, NaN] | [0, 1, 1, 0, NaN] |
| poblacion | 1234.0 | 1234.0 |
