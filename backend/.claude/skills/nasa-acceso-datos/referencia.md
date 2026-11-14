# Referencia — fuentes de datos

## Índice
1. Tabla de productos (verificada en CMR)
2. Volumen y método de recorte recomendado
3. MODIS vía AppEEARS
4. Población GPW v4.11
5. Cómo volver a verificar

---

## 1. Tabla de productos

Verificado con `earthaccess.search_datasets` / `search_data` (earthaccess 0.19.0) el **2026-11-13**.
"POR VERIFICAR" = no se pudo confirmar sin descargar un archivo con credenciales.

| Producto | short_name | Versión | concept-id | Proveedor | Cobertura en CMR | Formato del archivo | Abrir con |
|---|---|---|---|---|---|---|---|
| GPCP mensual 0.5° | `GPCPMON` | **3.3** (recomendada) | C3405935516-GES_DISC | GES_DISC | 1983-01 → 2025-12 | NetCDF4 `GPCPMON_L3_AAAAMM_V3.3.nc4` | `xr.open_dataset(..., engine="h5netcdf")` |
| GPCP mensual 0.5° | `GPCPMON` | 3.2 | C2211412414-GES_DISC | GES_DISC | 1983-01 → **2023-12** | NetCDF4 `..._V3.2.nc4` | ídem |
| MERRA-2 flujos superficie | `M2TMNXFLX` | 5.12.4 | C1276812868-GES_DISC | GES_DISC | 1980-01 → actual | NetCDF4 `MERRA2_<stream>.tavgM_2d_flx_Nx.AAAAMM.nc4` | ídem |
| MERRA-2 nivel único | `M2TMNXSLV` | 5.12.4 | C1276812859-GES_DISC | GES_DISC | 1980-01 → actual | NetCDF4 `MERRA2_<stream>.tavgM_2d_slv_Nx.AAAAMM.nc4` | ídem |
| IMERG Final mensual 0.1° | `GPM_3IMERGM` | 07 | C2723754851-GES_DISC | GES_DISC | 1998-01 → 2025-09 | HDF5 `3B-MO.MS.MRG.3IMERG.AAAAMMDD-...V07B.HDF5` | `engine="h5netcdf", group="Grid"` |
| IMERG Final diario 0.1° | `GPM_3IMERGDF` | 07 | C2723754864-GES_DISC | GES_DISC | 1998-01 → 2025-09 | NetCDF4 / HDF5 (POR VERIFICAR el grupo; en V07 diario la variable suele estar en la raíz) | probar primero sin `group`, si falla `group="Grid"` |
| GLDAS Noah 2.1 mensual 0.25° | `GLDAS_NOAH025_M` | 2.1 | C1342986036-GES_DISC | GES_DISC | 2000-01 → actual | NetCDF4 `GLDAS_NOAH025_M.AAAAMM.021.nc4` | `engine="h5netcdf"` |
| MODIS NDVI mensual 0.05° | `MOD13C2` | 061 | C2565788914-LPCLOUD | LPCLOUD | 2000-02 → actual | HDF4 (xarray no lo abre bien) → **usar AppEEARS** | ver §3 |
| MODIS cobertura del suelo 500 m | `MCD12Q1` | 061 | C2484079608-LPCLOUD | LPCLOUD | 2001 → actual (anual) | HDF4, malla sinusoidal → **usar AppEEARS** | ver §3 |
| GPW v4.11 población | `CIESIN_SEDAC_GPWv4_POPCOUNT_R11` | 4.11 | (consultar) | ESDIS | años 2000, 2005, 2010, 2015, 2020 | ZIP con GeoTIFF / ASCII / NetCDF | ver §4 |

**Decisión pendiente sobre GPCP:** el pedido original dice v3.2, pero **v3.2 termina en 2023-12** y el periodo del
proyecto llega a 2024-12. Usa v3.3 para 1983–2024, o acepta 1983–2023 con v3.2. **POR VERIFICAR:** que la variable
de v3.3 siga llamándose `sat_gauge_precip` (abre un archivo y revisa `ds.data_vars`).

Nombres de variable dentro de los archivos (del catálogo; **POR VERIFICAR** al abrir el primer archivo, porque
GES DISC no publica las variables en CMR): `sat_gauge_precip` (GPCP), `PRECTOTCORR` (FLX), `T2M` y `TQV` (SLV),
`precipitation` (IMERG), `SoilMoi0_10cm_inst`, `Evap_tavg` y `Qs_acc` (GLDAS).

Rasgos de las mallas que afectan al recorte:
- IMERG: dimensiones `(time, lon, lat)` → transponer. Longitudes −180..180.
- MERRA-2: malla 0.5° × 0.625°, lon −180..179.375.
- GLDAS: lat −60..90 (sin Antártida), océano = NaN (útil como máscara de tierra).
- GPCP: malla 0.5° global (comprueba el rango de longitudes al abrir).

## 2. Volumen y método de recorte

Tamaños de archivo observados en CMR (junio de 2024):

| Producto | MB por archivo | Archivos 2001–2024 | Total aproximado | Método recomendado |
|---|---|---|---|---|
| GPCPMON | ~7 | 288 (504 desde 1983) | 2–3.5 GB | descargar → recortar → borrar raw, archivo por archivo, o Harmony |
| M2TMNXFLX / SLV | ~75 | 288 (504 desde 1983) | 21–38 GB **por colección** | **Harmony u OPeNDAP con subconjunto de variables** |
| GPM_3IMERGM | ~18 | 288 | ~5 GB | Harmony / lectura perezosa con `earthaccess.open` |
| GPM_3IMERGDF | ~? (diario) | ~8 800 | decenas a cientos de GB | **año a año** con recorte en servidor; caché por año |
| GLDAS_NOAH025_M | ~24 | 288 | ~7 GB | Harmony / OPeNDAP con subconjunto de variables |

Patrón "descargar → recortar → borrar" (cuando no hay recorte en servidor): descarga un lote pequeño (p. ej. un año)
en `data/raw/`, ábrelo, recórtalo, conviértelo, añádelo a la caché y borra el lote. El disco nunca guarda el producto global entero.

Harmony (opcional, `pip install harmony-py`):

```python
from harmony import BBox, Client, Collection, Request
cliente = Client()  # usa ~/.netrc o EDL_USERNAME/EDL_PASSWORD
pedido = Request(collection=Collection(id="C1276812859-GES_DISC"),
                 spatial=BBox(oeste, sur, este, norte),
                 temporal={"start": datetime(2001, 1, 1), "stop": datetime(2024, 12, 31)},
                 variables=["T2M", "TQV"])
trabajo = cliente.submit(pedido)
rutas = [f.result() for f in cliente.download_all(trabajo, directory="data/raw/M2TMNXSLV")]
```

Comprueba que la colección tenga servicio Harmony con `earthaccess.search_services` o en la página de la colección;
si no lo tiene, usa el patrón anterior.

## 3. MODIS vía AppEEARS

AppEEARS (API REST, `https://appeears.earthdatacloud.nasa.gov/api/`) recorta, reproyecta a geográficas y entrega
NetCDF, lo que evita el HDF4 y la malla sinusoidal de MODIS. Usa las mismas credenciales de Earthdata.

1. `POST /login` con autenticación básica → `token` (Bearer). Lee usuario y contraseña de las variables de entorno o
   de `.netrc`, nunca de un literal.
2. Consulta las capas: `GET /product/MOD13C2.061` y `GET /product/MCD12Q1.061`. Los nombres de capa usan guiones
   bajos (p. ej. `CMG_0_05_Deg_Monthly_NDVI`, `LC_Type1`). **POR VERIFICAR** con esta llamada antes de fijarlos.
3. `POST /task` con:
   ```json
   {"task_type": "area", "task_name": "ndvi_sahel_2001_2024",
    "params": {"dates": [{"startDate": "01-01-2001", "endDate": "12-31-2024"}],
               "layers": [{"product": "MOD13C2.061", "layer": "CMG_0_05_Deg_Monthly_NDVI"}],
               "geo": {"type": "FeatureCollection", "features": [ ...polígono de la región... ]},
               "output": {"format": {"type": "netcdf4"}, "projection": "geographic"}}}
   ```
   (Las fechas de AppEEARS van en formato `MM-DD-AAAA`.)
4. Consulta `GET /task/{task_id}` hasta `status == "done"` (espera ≥ 30 s entre consultas; puede tardar minutos u horas).
5. `GET /bundle/{task_id}` → lista de archivos; descarga cada `file_id` con `GET /bundle/{task_id}/{file_id}` a `data/raw/appeears/`.
6. Abre el NetCDF, normaliza, convierte (NDVI × 0.0001; LC_Type1 → máscara de clases 12 y 14) y guarda en caché.

## 4. Población GPW v4.11

- Colección `CIESIN_SEDAC_GPWv4_POPCOUNT_R11` (54 gránulos en CMR, uno por año × resolución × formato).
- Recomendado: `gpw-v4-population-count-rev11_totpop_15_min_nc.zip` (~6.5 MB, 0.25°, todos los años en un NetCDF)
  o `..._totpop_2pt5_min_nc.zip` (~119 MB) si el mapa es más fino que 0.25°. Para conservar el total al regrillar
  (skill `escaner-y-mapas`), la malla de población debe ser **igual o más fina** que la del mapa.
- El NetCDF de GPW trae una dimensión `raster` que mezcla los años de población con capas de calidad de datos.
  **POR VERIFICAR** qué índice de `raster` corresponde a cada año: consulta el archivo de documentación incluido en el ZIP
  o los atributos de la variable antes de elegir 2020.
- Descomprime en `data/raw/gpw/`; guarda en caché `data/cache/poblacion_global_2020_2020.nc` con `attrs["units"] = "personas"`.
- Es un **conteo por celda** (personas), no una densidad: al regrillar se **suma**, nunca se promedia.

## 5. Cómo volver a verificar

```bash
.venv/Scripts/python -c "import earthaccess; [print(c['umm']['ShortName'], c['umm']['Version'], c['meta']['concept-id']) for s in ['GPCPMON','M2TMNXFLX','M2TMNXSLV','GPM_3IMERGM','GPM_3IMERGDF','GLDAS_NOAH025_M','MOD13C2','MCD12Q1','CIESIN_SEDAC_GPWv4_POPCOUNT_R11'] for c in earthaccess.search_datasets(short_name=s)]"
```

Actualiza la tabla de §1 y la fecha si algo cambia.
