---
name: catalogo-variables
description: Úsala al agregar, consultar, validar o convertir variables de catalogo.yaml (id, grupo lluvia/causa/agua/social/calculada, short_name, variable del archivo, unidad original, conversión, unidad final, frecuencia) o al escribir motor/catalogo.py, y siempre que haya que saber en qué unidad viene una variable de NASA o cómo pasarla a mm/día, mm/mes o °C.
---

# Catálogo de variables

## Objetivo

`catalogo.yaml` es la **única** descripción de cada variable del proyecto: de dónde viene, cómo se llama dentro
del archivo, en qué unidad llega y cómo se convierte. `motor/catalogo.py` lo carga, lo valida y aplica las
conversiones. Si una conversión vive solo aquí, un error de unidades se corrige en un solo sitio, y la interfaz puede
mostrar `nombre_simple` y `definicion_simple` sin duplicar textos.

Tabla completa de variables y unidades válidas: [referencia.md](referencia.md).
Catálogo inicial listo para copiar a la raíz: [scripts/catalogo_ejemplo.yaml](scripts/catalogo_ejemplo.yaml).

## Esquema de cada variable

```yaml
variables:
  - id: lluvia_merra2              # único, snake_case; se usa en nombres de caché y en el JSON del motor
    grupo: lluvia                  # lluvia | causa | agua | social | calculada
    nombre_simple: Lluvia (MERRA-2)
    definicion_simple: Cuánta agua cae del cielo cada día, según un modelo que combina observaciones.
    dataset: MERRA-2 tavgM_2d_flx_Nx
    short_name: M2TMNXFLX          # null solo en grupo "calculada"
    version: "5.12.4"              # opcional, pero recomendado (verificado con search_datasets)
    variable: PRECTOTCORR          # nombre EXACTO en el archivo (o capa AppEEARS)
    unidad_original: kg m-2 s-1
    conversion: {op: factor, valor: 86400}
    unidad_final: mm/dia
    desde: "1980-01"               # AAAA-MM (o AAAA para anuales)
    resolucion: 0.5° x 0.625°
    frecuencia: mensual            # diaria | mensual | anual
```

Obligatorios: `id, grupo, nombre_simple, definicion_simple, dataset, short_name, variable, unidad_original,
conversion, unidad_final, desde, resolucion, frecuencia`. Opcionales: `version`, `acceso`
(`earthaccess` por defecto | `appeears` | `sedac`), `origen` e `indicador` (solo para el grupo `calculada`) y `notas`.

## Conversiones: lista blanca, sin `eval`

`conversion` es un dict con `op` de una lista cerrada. Así un YAML nunca ejecuta código y cada operación tiene un test.

| op | efecto | ejemplo |
|---|---|---|
| `ninguna` | no cambia los valores (solo la etiqueta de unidad si difiere: kg m-2 = mm) | `{op: ninguna}` |
| `factor` | `x · valor` | `{op: factor, valor: 86400}` |
| `suma` | `x + valor` | `{op: suma, valor: -273.15}` |
| `dias_del_mes` | `x · días del mes de cada fecha` (usa `time.dt.days_in_month`, con años bisiestos) | `{op: dias_del_mes}` |
| `clases` | `1.0` si `x ∈ valores`, `0.0` si no, NaN si x es NaN | `{op: clases, valores: [12, 14]}` |

## API (convención del proyecto)

```python
def cargar_catalogo(ruta: str | Path = "catalogo.yaml") -> dict[str, dict]: ...   # {id: entrada}, validado
def validar_entrada(entrada: dict) -> list[str]: ...                               # lista de errores; [] = válida
def convertir(da: xr.DataArray, entrada: dict) -> xr.DataArray: ...                # attrs["units"] = unidad_final
def variables_por_grupo(catalogo: dict[str, dict], grupo: str) -> list[str]: ...
```

- `cargar_catalogo` junta **todos** los errores y lanza un único `ValueError` que los enumera ("lluvia_gpcp: falta
  'unidad_final'; temp_aire: unidad 'Kelvin' desconocida"). Así se corrigen de una vez, no uno por ejecución.
- Valida: campos obligatorios, `id` único, `grupo` y `frecuencia` dentro de su conjunto, `unidad_original` y
  `unidad_final` dentro de `UNIDADES_CONOCIDAS`, `op` conocida con sus parámetros (`valor` numérico, `valores` lista
  de enteros), `desde` con formato `AAAA-MM` o `AAAA` y `short_name` no nulo salvo en `calculada`.
- `convertir` **no modifica** el DataArray de entrada (devuelve uno nuevo), guarda la unidad que traía el archivo en
  `attrs["units_archivo"]` y pone `attrs["units"] = entrada["unidad_final"]`. No compara con la unidad del archivo
  porque NASA la escribe de muchas formas ("mm/hr", "kg m-2 s-1", "K").
- Unidades en ASCII y siempre con la misma grafía (`mm/dia`, no `mm/día` ni `mm d-1`), porque se comparan como
  texto en `series.py` (p. ej. para decidir si se puede sumar).

## Errores comunes

- **GPCP × 30 fijo** en vez de los días reales del mes: febrero sale un 7 % alto. Usa `dias_del_mes`.
- **IMERG mensual × 24 olvidado**: viene en mm/h; sin convertir, la lluvia parece 24 veces menor.
- **Qs_acc de GLDAS**: es lo acumulado en 3 h (promedio del mes): × 8 → mm/día. No × 86400.
- **NDVI sin escalar** (valores de miles): × 0.0001. Los valores de relleno (p. ej. −3000) deben ser NaN **antes**
  de escalar; revisa `_FillValue` y `valid_range` al abrir.
- **LC_Type1 promediado como número**: es una clase, no una cantidad. Primero `clases` (1/0) y luego, si hace falta,
  la fracción de celdas de cultivo.
- **Convertir dos veces** (al descargar y otra vez al leer la caché): la caché ya guarda unidades finales;
  `convertir` solo se llama en `datos.obtener_variable` justo tras abrir datos crudos.

## Cómo probar

- `tests/test_catalogo.py`: carga `catalogo.yaml` sin errores; un YAML con un campo faltante, una unidad
  desconocida, un `op` desconocido y un `id` repetido lanza `ValueError` que menciona los cuatro problemas.
- Un test por conversión del catálogo con un valor de ejemplo calculado a mano (ver la tabla de la skill
  `validacion-y-pruebas`), por ejemplo `1e-4 kg m-2 s-1 → 8.64 mm/dia`, `300 K → 26.85 degC`,
  `2 mm/dia en febrero de 2024 → 58 mm/mes`.
