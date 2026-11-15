# Referencia — Estado, errores, caché y precarga OPeNDAP en RAM

## 1. Endpoints de estado y administración

| Método | Ruta | Resumen |
|---|---|---|
| `GET` | `/` | Información general de la API, versión (`0.2.0`), datasets y lista de IDs de variables |
| `GET` | `/api/v1/salud` | Estado del servidor, uso de caché RAM y disponibilidad de credenciales NASA Earthdata |
| `GET` | `/api/v1/opendap/consulta` | Índices espaciales `[lat0:1:lat1]`, `[lon0:1:lon1]` y URLs DAP4/DAP2 sin descargar |
| `GET` | `/api/v1/cache` | Inventario de cubos actualmente en la caché LRU de memoria RAM (`kb_ram_total`, `entradas`) |
| `DELETE` | `/api/v1/cache` | Vacía la caché LRU en memoria RAM (completa o filtrada por `?variable=`) |
| `POST` | `/api/v1/opendap/precargar` | Lanza una tarea en segundo plano (202 Accepted) para descargar de OPeNDAP a RAM |
| `POST` | `/api/v1/descargas` | Alias exacto de `POST /api/v1/opendap/precargar` |
| `GET` | `/api/v1/descargas` | Lista todas las tareas OPeNDAP recientes y en curso |
| `GET` | `/api/v1/descargas/{tarea_id}` | Estado y progreso de una tarea OPeNDAP específica |

---

## 2. Outputs reales de estado y salud

### `GET /` (`200 OK`)
```json
{
  "nombre": "NASA Space Apps — Las Dos Caras de la Lluvia API",
  "version": "0.2.0",
  "modo_acceso": "opendap_memoria_sin_archivos",
  "documentacion": "/docs",
  "prefijo_api": "/api/v1",
  "datasets": ["gpcp", "merra2", "gldas", "imerg"],
  "variables": [
    "lluvia_gpcp",
    "lluvia_merra2",
    "temp_aire",
    "vapor_agua",
    "humedad_suelo",
    "evapotranspiracion",
    "lluvia_imerg_mes",
    "lluvia_imerg_dia",
    "cdd_imerg",
    "r20mm_imerg",
    "dias_humedos_imerg",
    "prcptot_imerg",
    "sdii_imerg"
  ]
}
```

### `GET /api/v1/salud` (`200 OK`)
```json
{
  "estado": "ok",
  "modo_acceso": "opendap_memoria",
  "almacenamiento_disco": false,
  "n_datasets": 4,
  "n_variables": 13,
  "cubos_en_memoria_ram": 0,
  "kb_en_memoria_ram": 0.0,
  "max_cubos_ram": 128,
  "credenciales_earthdata": {
    "variables_entorno": false,
    "netrc": false,
    "listo": false
  }
}
```
> **Uso en UI**: si `credenciales_earthdata.listo === false`, las peticiones con `descargar=true` no podrán autenticarse contra NASA GES DISC; el frontend puede usar `sintetico=true` automáticamente en ese caso.

---

## 3. Outputs reales de error

### `400 Bad Request` — `parametro_invalido`
Ejemplo al enviar un bbox incompleto (`GET /api/v1/series/lluvia_gpcp?oeste=-100`) o una fecha con día (`inicio=2001-01-01`):
```json
{
  "error": "parametro_invalido",
  "mensaje": "Si especificas coordenadas de caja, debes enviar las cuatro: oeste, sur, este y norte."
}
```

### `404 Not Found` — `datos_no_disponibles_en_memoria`
Ejemplo al consultar sin `sintetico=true` ni `descargar=true` cuando el cubo no está en RAM:
```json
{
  "error": "datos_no_disponibles_en_memoria",
  "mensaje": "lluvia_gpcp en 'noreste_mexico' (2001-01 → 2024-12) no está en la caché en memoria RAM. Pasa descargar=true para consultarla en vivo por OPeNDAP, envía POST /api/v1/descargas para precargarla en RAM, o usa ?sintetico=true en modo demo.",
  "variable": "lluvia_gpcp",
  "region": "noreste_mexico",
  "periodo": ["2001-01", "2024-12"],
  "sugerencia": "Pasa ?descargar=true para consultar en vivo por OPeNDAP en memoria RAM, envía POST /api/v1/opendap/precargar, o añade ?sintetico=true durante el desarrollo del frontend."
}
```

### `404 Not Found` — `no_encontrado`
```json
{
  "error": "no_encontrado",
  "mensaje": "Variable 'no_existe' no existe en el catálogo (válidas: ['cdd_imerg', 'dias_humedos_imerg', 'evapotranspiracion', 'humedad_suelo', 'lluvia_gpcp', 'lluvia_imerg_dia', 'lluvia_imerg_mes', 'lluvia_merra2', 'prcptot_imerg', 'r20mm_imerg', 'sdii_imerg', 'temp_aire', 'vapor_agua'])"
}
```

### `422 Unprocessable Entity` — `serie_rechazada`
Cuando la serie supera el umbral de datos faltantes (> 10 %):
```json
{
  "error": "serie_rechazada",
  "mensaje": "Serie rechazada por calidad: fracción faltante 0.25 > 0.10",
  "reporte": {
    "aceptada": false,
    "n_esperados": 288,
    "n_faltantes": 72,
    "fraccion_faltante": 0.25,
    "motivo": "fraccion_faltante_excedida"
  }
}
```

### `422 Unprocessable Entity` — Validación FastAPI (`detail`)
Ejemplo con `alfa=0.9`:
```json
{
  "detail": [
    {
      "type": "less_than",
      "loc": ["query", "alfa"],
      "msg": "Input should be less than 0.5",
      "input": "0.9",
      "ctx": { "lt": 0.5 }
    }
  ]
}
```

---

## 4. Esquema de `POST /api/v1/opendap/precargar`

### Request Body (`PeticionDescargaDTO`)
```json
{
  "variable": "lluvia_gpcp",
  "region": "noreste_mexico",
  "bbox": null,
  "inicio": "2001-01",
  "fin": "2024-12",
  "forzar": false,
  "sincrono": false
}
```
- Si es una región dibujada por el usuario, envía `"region": "mi_region"` y `"bbox": [-101.0, 22.0, -97.0, 27.0]`.
- Respuesta (`202 Accepted`): objeto de tarea con `id`, `variable`, `region`, `periodo`, `estado` (`"pendiente" | "ejecutando" | "completada" | "error"`), `mensaje` y `actualizado_en`.

