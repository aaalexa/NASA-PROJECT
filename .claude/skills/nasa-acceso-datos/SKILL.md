---
name: nasa-acceso-datos
description: Úsala al descargar, buscar, abrir o cachear datos de NASA Earthdata con earthaccess (GPCP, MERRA-2, GPM IMERG, GLDAS, MODIS vía AppEEARS, población GPW de SEDAC), al configurar credenciales (.netrc, EARTHDATA_USERNAME/EARTHDATA_PASSWORD), al recortar por bounding box con OPeNDAP o Harmony, al abrir HDF5/NetCDF con xarray o al leer y escribir la caché de data/ (motor/datos.py), aunque solo se diga "bajar datos" o se mencione un short_name.
---

# Acceso a datos de NASA Earthdata

## Objetivo

`motor/datos.py` entrega al resto del motor un `xarray.DataArray` **ya recortado a la región, con coordenadas
normalizadas y en las unidades finales del catálogo**, descargando lo mínimo posible y sin repetir descargas.
El resto del motor nunca habla con la red: si algo falla aquí, falla en un único sitio y con un mensaje claro.

Fuentes, short_names, formatos y método de recorte de cada producto: [referencia.md](referencia.md).
Esqueleto de código: [scripts/plantilla_datos.py](scripts/plantilla_datos.py) (es una plantilla: pruébala con
datos reales antes de darla por buena).

## Pasos

### 1. Credenciales (nunca en el código)

```python
import earthaccess
auth = earthaccess.login(strategy="environment")   # EARTHDATA_USERNAME / EARTHDATA_PASSWORD
if not auth.authenticated:
    auth = earthaccess.login(strategy="netrc")      # ~/.netrc (Windows: %USERPROFILE%\_netrc o .netrc)
```

- No uses `strategy="interactive"` dentro de la app Streamlit: se quedaría esperando una contraseña en la terminal.
- Si ninguna estrategia funciona, lanza un error que diga qué variable o archivo configurar, sin mostrar valores.
- `.gitignore` debe contener `.netrc`, `_netrc`, `.env` y `data/`. Las credenciales filtradas a git quedan en el
  historial aunque se borren después, y en un hackathon el repositorio suele ser público.

### 2. Verificar el producto antes de fijarlo en el código

Los short_names y las versiones cambian (IMERG pasó de V06 a V07; SEDAC migró a Earthdata). Antes de escribir un
`short_name` o una `version` en `catalogo.yaml`, compruébalo:

```python
for c in earthaccess.search_datasets(short_name="GPM_3IMERGM"):
    print(c["umm"]["ShortName"], c["umm"]["Version"], c["meta"]["concept-id"], c["meta"]["provider-id"])
```

`search_datasets` consulta el catálogo público CMR y **no necesita credenciales**. Anota en `referencia.md` la
versión confirmada y la fecha de la comprobación.

### 3. Buscar gránulos

```python
resultados = earthaccess.search_data(
    short_name="GPM_3IMERGM", version="07",
    temporal=("2001-01-01", "2024-12-31"),
    bounding_box=(oeste, sur, este, norte),      # orden de earthaccess: lon_min, lat_min, lon_max, lat_max
)
```

**Ojo:** en productos **globales**, `bounding_box` solo filtra qué gránulos se listan; **cada archivo sigue siendo
global**. Para descargar menos hay que recortar en el servidor o leer de forma perezosa (paso 4).

### 4. Descargar solo la región (elegir el primer método que aplique)

1. **Caché**: si `data/cache/<variable>_<region>_<inicio>_<fin>.nc` (o `.zarr`) existe, léelo y termina.
2. **Harmony** (recorte espacial y por variable en el servidor; para productos de GES DISC como MERRA-2, IMERG
   y GLDAS): `harmony-py` con `Request(collection=Collection(id=concept_id), spatial=BBox(oeste, sur, este, norte),
   temporal={"start": ..., "stop": ...}, variables=[...])`. Si lo usas, añade `harmony-py` con versión fija a
   `requirements.txt`.
3. **OPeNDAP / lectura perezosa**: `earthaccess.open(resultados)` devuelve archivos remotos; ábrelos con xarray,
   haz `.sel()` de la región y la variable y escribe solo eso. Útil cuando no hay Harmony.
4. **Descarga completa** a `data/raw/<short_name>/` con `earthaccess.download(resultados, local_path=...)`, solo si
   el volumen total es pequeño (orden de 1–2 GB como mucho; p. ej. GPCP mensual). Recorta y guarda en caché enseguida.

La lluvia **diaria** global de 24 años (IMERG diario, ~8 800 archivos) **no se descarga entera**: procesa año a año,
recorta cada año y guarda una caché por año antes de pasar al siguiente. Así una interrupción no obliga a empezar de nuevo.

### 5. Abrir con xarray y normalizar

- **IMERG (HDF5 con grupos)**: `xr.open_dataset(ruta, engine="h5netcdf", group="Grid")`. Sus dimensiones vienen
  como `(time, lon, lat)`: transpón a `(time, lat, lon)`.
- NetCDF4 (GPCP, MERRA-2, GLDAS): `xr.open_dataset(ruta, engine="h5netcdf")` (o `netcdf4`). Varios archivos:
  `xr.open_mfdataset(rutas, combine="by_coords")`.
- `normalizar_coordenadas(da)`: renombra `latitude/longitude` (o `y/x`) a `lat/lon`, pasa la longitud a
  [−180, 180) y ordena, ordena la latitud de forma ascendente y deja el orden `(time, lat, lon)`. Todo el proyecto
  asume esta convención.
- **Convierte unidades justo después de abrir** con `catalogo.convertir(da, entrada)` (skill `catalogo-variables`),
  que deja `attrs["units"]` en la unidad final. Así ninguna función posterior ve unidades crudas.

### 6. Guardar en caché

- Nombre: `data/cache/<variable>_<region>_<inicio>_<fin>.<ext>`, con `variable` = `id` del catálogo,
  `region` = slug en minúsculas sin espacios (`sahel`, `noreste_mexico`), `inicio` y `fin` = `AAAA-MM`.
  Ejemplo: `data/cache/lluvia_gpcp_sahel_1983-01_2024-12.nc`.
- `.nc` para series y cubos pequeños; `.zarr` para cubos grandes (diarios o mapas por píxel).
- **Escritura atómica**: escribe en `<nombre>.tmp` y luego renómbralo. Una descarga interrumpida no debe dejar un
  archivo a medias que la siguiente ejecución tome por bueno.
- `data/raw/` contiene las descargas crudas (se pueden borrar); `data/cache/`, los datos recortados y convertidos.
  Toda la carpeta `data/` va en `.gitignore`.

## API (convención del proyecto)

```python
BBox = tuple[float, float, float, float]        # (oeste, sur, este, norte) en grados, lon en [-180, 180)

def iniciar_sesion() -> earthaccess.Auth: ...
def ruta_cache(variable: str, region: str, inicio: str, fin: str, formato: str = "nc") -> Path: ...
def normalizar_coordenadas(da: xr.DataArray) -> xr.DataArray: ...
def obtener_variable(variable: str, region: str, bbox: BBox, inicio: str, fin: str,
                     catalogo: dict) -> xr.DataArray: ...   # unidades finales en attrs["units"]
```

MODIS (AppEEARS) y la población GPW tienen su propio flujo (ver referencia.md §3 y §4), pero también terminan en
`obtener_variable` con la misma caché y la misma normalización.

## Errores comunes

- **Orden del bounding box**: earthaccess usa `(lon_min, lat_min, lon_max, lat_max)`; mucha gente escribe lat primero.
- **Longitudes 0–360** (algunos productos) frente a −180–180: un `sel(lon=slice(-110, -90))` devuelve vacío sin avisar.
- **Latitud descendente**: `sel(lat=slice(10, 20))` devuelve vacío si la latitud va de 90 a −90. Normaliza antes de recortar.
- **Olvidar `group="Grid"`** en IMERG: el Dataset sale vacío o sin `precipitation`.
- **Confiar en `bounding_box` para reducir la descarga** de productos globales (ver paso 3).
- **Fijar una versión sin verificarla**: la búsqueda devuelve 0 gránulos y el error aparece mucho después.
- **Caché sin unidades**: guarda siempre después de convertir, con `attrs["units"]`, para que leer la caché dé lo mismo que descargar.
- **Credenciales en notebooks o en `print`**: no las muestres ni en logs de depuración.

## Cómo probar

- Tests **sin red**: `ruta_cache` (formato del nombre), `normalizar_coordenadas` (con un DataArray sintético que
  tenga lon 0–360, lat descendente y dims `(time, lon, lat)`) y la lógica de "si existe la caché, no descargar"
  (con `monkeypatch` sobre `earthaccess.search_data` para comprobar que no se llama).
- Test **con red**, marcado `@pytest.mark.red` y omitido por defecto: `search_datasets` de cada short_name del
  catálogo devuelve al menos una colección con la versión esperada.
- Comprobación manual: descargar 1 año de GPCP de una región pequeña, revisar `da.attrs["units"]`, el rango de
  valores (lluvia ≥ 0, valores plausibles en mm/mes) y que una segunda llamada lee la caché sin tocar la red.
