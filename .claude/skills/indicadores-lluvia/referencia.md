# Referencia — indicadores de lluvia

## 1. Definiciones (ETCCDI, adaptadas)

Para un año con días d = 1..D (D = 365 o 366) y lluvia P_d en mm/dia:

```
seco_d    = P_d < 1            (y P_d no es NaN)
humedo_d  = P_d ≥ 1
intenso_d = P_d ≥ 20
CDD     = max longitud de una secuencia de días consecutivos con seco_d = True, dentro del año
R20mm   = Σ_d intenso_d
W       = Σ_d humedo_d
PRCPTOT = Σ_d P_d · humedo_d                     [mm/anio]
SDII    = PRCPTOT / W   si W > 0, si no NaN      [mm/dia]
```

Calidad: si `n_NaN / D > 0.10`, todos los índices del año = NaN.

## 2. CDD vectorizado (suma acumulada con reinicio)

Idea: llevar un contador que suma 1 en cada día seco y vuelve a 0 en cada día no seco; la CDD es su máximo.

```python
def racha_seca_maxima(seco: np.ndarray) -> np.ndarray:
    """Racha máxima de True consecutivos a lo largo del último eje. seco: bool. Devuelve int (días)."""
    if seco.shape[-1] == 0:
        return np.zeros(seco.shape[:-1], dtype=np.int64)
    c = np.cumsum(seco, axis=-1, dtype=np.int64)          # días secos acumulados
    reinicio = np.where(seco, 0, c)                         # en días no secos, anota el acumulado
    base = np.maximum.accumulate(reinicio, axis=-1)         # último acumulado en un día no seco
    return (c - base).max(axis=-1)
```

Ejemplo: `seco = [T, T, F, T, T, T, F]`
`c = [1,2,2,3,4,5,5]`, `reinicio = [0,0,2,0,0,0,5]`, `base = [0,0,2,2,2,2,5]`, `c − base = [1,2,0,1,2,3,0]` → **3**.

Aplicación por año y por píxel:

```python
seco = (pr < 1) & pr.notnull()
cdd = seco.groupby("time.year").map(
    lambda g: xr.apply_ufunc(racha_seca_maxima, g, input_core_dims=[["time"]],
                             dask="parallelized", output_dtypes=[np.int64])
).rename(year="anio")
```

Para dask, el eje `time` de cada año debe estar en un solo bloque (`pr.chunk({"time": -1})`, o al menos 366 días por bloque).

## 3. Casos calculados a mano (para los tests)

### Caso A — año normal (2001, 365 días)

Todos los días 0 mm excepto:

| fecha | P (mm) |
|---|---|
| 2001-01-06 | 5 |
| 2001-01-07 | 25 |
| 2001-01-08 | 0.5 |
| 2001-03-01 | 20 |
| 2001-07-15 | 25 |

Entonces: W = 4 (5, 25, 20, 25), PRCPTOT = 75, SDII = 18.75, R20mm = 3 (25, 20, 25).
CDD: la racha más larga va del 2001-07-16 al 2001-12-31 = **169 días**.
(Rachas: 1–5 ene = 5; 8 ene–28 feb = 52 (el 0.5 del 8 de enero es seco); 2 mar–14 jul = 135; 16 jul–31 dic = 169.)

### Caso B — umbrales

`P = [1.0, 0.99, 20.0, 19.99]` y el resto del año 0: W = 3 (1.0, 20.0, 19.99), R20mm = 1, PRCPTOT = 40.99.

### Caso C — año sin lluvia

2001 todo 0: CDD = 365, R20mm = 0, W = 0, PRCPTOT = 0, SDII = NaN. 2004 (bisiesto) todo 0: CDD = 366.

### Caso D — racha que cruza el año

2001 y 2002 con P = 5 mm todos los días, salvo del 2001-12-22 al 2002-01-05 (15 días) con 0 mm.
CDD(2001) = 10 (22–31 dic), CDD(2002) = 5 (1–5 ene). Con cortar_en_anio=False sería 15, asignado a 2002.

### Caso E — faltantes

- 2001 con 37 días NaN (10.1 %) → todos los índices NaN.
- 2001 todo 0 excepto un NaN el 2001-07-01: CDD = max(181, 183) = **183** (1 ene–30 jun = 181 días;
  2 jul–31 dic = 183 días); W = 0; el año se acepta (1 NaN < 10 %).
