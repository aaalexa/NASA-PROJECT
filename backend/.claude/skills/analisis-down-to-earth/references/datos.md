# Datos: productos, conversiones y límites

## Variables y productos

| Código | Variable | Producto | Campo | Unidad original | Conversión (una sola vez) | Unidad mensual |
|---|---|---|---|---|---|---|
| P | Precipitación | GPCP mensual v3.3 (GPCPMON) | `sat_gauge_precip` | mm/día | × días del mes | mm/mes |
| T | Temperatura del aire a 2 m | MERRA-2 mensual (M2TMNXSLV) | `T2M` | K | − 273.15 | °C |
| SM | Humedad del suelo 0–10 cm | GLDAS Noah mensual 2.1 | `SoilMoi0_10cm_inst` | kg/m² | ÷ 100 | m³/m³ |
| ET | Evapotranspiración real | GLDAS Noah mensual 2.1 | `Evap_tavg` | kg/m²/s | × 86 400 × días del mes | mm/mes |

"Días del mes" son los días reales (28, 29, 30 o 31), con febrero de 29 días en los bisiestos (2004, 2008, 2012,
2016, 2020, 2024). Usar 30 fijo introduce errores de hasta un 10 % en febrero.

Por qué SM ÷ 100: 1 kg/m² de agua = 1 mm de lámina; la capa mide 100 mm (0–10 cm), así que kg/m² ÷ 100 mm es la
fracción volumétrica m³/m³.

### Controles de conversión (deben dar exactamente esto)

- 2 mm/día en un mes de 30 días = **60 mm/mes**
- 300 K = **26.85 °C**
- 20 kg/m² = **0.20 m³/m³**
- 0.00001 kg/m²/s en 30 días = 0.00001 × 86 400 × 30 = **25.92 mm/mes**

### Señales de que una columna no está en la unidad que dice

- T ≈ 250–320 → sigue en K. T ≈ −250 → se restó 273.15 dos veces.
- SM ≈ 5–50 → sigue en kg/m². SM ≈ 0.002 → se dividió dos veces.
- ET ≈ 1e-6–1e-4 → sigue en kg/m²/s. ET en miles de mm/mes → se multiplicó dos veces.
- P ≈ 0–15 todos los meses en una región húmeda → posiblemente mm/día sin convertir.

## Período

Enero 2001 – diciembre 2024: 288 meses, 24 años. Antes de analizar, comprueba que los tres productos tienen datos en
todo el período (GLDAS 2.1 empieza en 2000; MERRA-2 cubre 2001–2024). La especificación original pedía GPCP v3.2,
pero la v3.2 termina en 2023-12; se usa **GPCP v3.3**, que llega a 2025 y conserva el campo `sat_gauge_precip`.
Dilo al presentar resultados. **No es una normal
climatológica de 30 años**: las medias y anomalías son relativas a 2001–2024.

## Límites físicos (deben acompañar los resultados)

- **SM es solo 0–10 cm**: la capa superficial reacciona rápido a la lluvia y al calor; no representa la zona de
  raíces ni el agua subterránea.
- **ET es real, no potencial**: es lo que se evaporó y transpiró, limitado por el agua disponible. No sirve como
  PET para SPEI ni para índices de demanda atmosférica.
- **SM y ET de GLDAS comparten modelo (Noah) y entradas** (forzantes meteorológicos, incluida la lluvia): su
  coincidencia no es una confirmación independiente.
- **ET no sube necesariamente con el calor**: con suelo seco puede bajar aunque T suba.
- **T es temperatura del aire a 2 m** del reanálisis MERRA-2, no temperatura de la superficie.
- **P (GPCP) y ET (GLDAS) vienen de fuentes distintas**: P − ET no es un balance hídrico cerrado (faltan
  escorrentía y cambio de almacenamiento, y los errores de cada producto no se cancelan).
- Con estos datos no se clasifican sequías ni inundaciones.

## Limpieza

- Valores de relleno → faltante (NaN): −9999, −999, 9.999e20, 1e15 o más, `_FillValue`/`missing_value` del
  NetCDF, textos vacíos o "NA". **Nunca** se convierten en 0 ni se interpolan.
- Ceros exactos en un **promedio regional** de P, ET o SM son sospechosos: casi siempre son faltantes que alguien
  rellenó. Adviértelo y compruébalo antes de seguir.
- Fechas: normaliza a año-mes (GPCP y GLDAS fechan el día 1, MERRA-2 puede traer hora; `2001-01-01T00:30` es
  enero de 2001). Duplicados con valores distintos → faltante y advertencia, no un promedio silencioso.
- Une las cuatro variables **por año y mes**, nunca por posición de fila.

## Promedio regional

Las tres fuentes tienen rejillas distintas (GPCP 0.5°, MERRA-2 0.5° × 0.625°, GLDAS 0.25°). Para que las cuatro
series describan el mismo territorio:

1. Usa **el mismo polígono terrestre** para las tres fuentes (no un bounding box distinto para cada una).
2. Para cada celda i, calcula **Aᵢ = área de la celda que cae dentro del polígono** (no solo cos(lat): una celda
   que está medio fuera debe pesar la mitad). Con regionmask/rioxarray: fracción de solape × área esférica de la
   celda (∝ Δlon · |sin(lat₂) − sin(lat₁)|).
3. Media regional en cada mes: **X = Σ(Aᵢ·Xᵢ)/Σ(Aᵢ)**, sumando solo las celdas con dato válido.
4. Registra la **fracción de área válida** = Σ(Aᵢ válidas)/Σ(Aᵢ). Si cambia con el tiempo (celdas que aparecen o
   desaparecen), la media puede tener una tendencia artificial: adviértelo. El script la acepta en columnas
   `fraccion_area` o `fraccion_area_<VAR>`.

En el backend: `motor/series.py: pesos_area_region` (área esférica de cada celda recortada a la caja) ×
`fraccion_tierra_desde_malla` (fracción de cada celda de GPCP/MERRA-2 cubierta por las subceldas de tierra de
GLDAS 0.25°, la misma huella que usan SM y ET), aplicados en `promedio_area(..., pesos=...)`. Las celdas cuyo centro
cae fuera de la caja no se incluyen (aproximación de borde).

## Archivos de salida

- **CSV mensual**: fecha, P (mm/mes), T (°C), SM (m³/m³), ET (mm/mes) y las anomalías z; vacíos donde falta.
- **CSV anual**: año, P (mm/año), T (°C), SM (m³/m³), ET (mm/año), marca de año completo por variable y si entra en
  el tramo de tendencias.
