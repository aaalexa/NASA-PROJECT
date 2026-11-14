import json, sys, pathlib
sys.path.insert(0, "src")
from fastapi.testclient import TestClient
from core.api.app import app
c = TestClient(app)
out = pathlib.Path("../docs/api")
(out/"openapi.json").write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2))
S = "sintetico=true"
casos = {
 "raiz": "/",
 "salud": "/api/v1/salud",
 "catalogo": "/api/v1/catalogo",
 "catalog_dte": "/catalog",
 "datasets": "/api/v1/datasets",
 "variables": "/api/v1/variables?solo_analizables=true",
 "variable_detalle": "/api/v1/variables/lluvia_gpcp",
 "regiones": "/api/v1/regiones?zona=mexico_centroamerica",
 "region_detalle": "/api/v1/regiones/noreste_mexico",
 "calcular_bbox": "/api/v1/regiones/calcular-bbox?oeste=-101&sur=22&este=-97&norte=27&nombre=mi_zona",
 "serie": f"/api/v1/series/lluvia_gpcp?region=noreste_mexico&inicio=2001-01&fin=2024-12&{S}",
 "serie_anual": f"/api/v1/series/lluvia_gpcp?region=noreste_mexico&anual=suma&{S}",
 "tendencia": f"/api/v1/tendencias/lluvia_gpcp?region=noreste_mexico&{S}",
 "indicadores": f"/api/v1/indicadores?region=noreste_mexico&{S}",
 "escaner": f"/api/v1/escaner?region=noreste_mexico&{S}",
 "dos_caras": f"/api/v1/dos-caras?variable=lluvia_gpcp&region_a=sahel&region_b=sureste_mexico&{S}",
 "mapa": f"/api/v1/mapas/lluvia_gpcp?region=noreste_mexico&{S}",
 "demo_result": f"/demo/result?region=corredor_seco_centroamericano&{S}",
 "opendap_consulta": "/api/v1/opendap/consulta?variable=lluvia_gpcp&region=noreste_mexico",
 "cache": "/api/v1/cache",
 "descargas": "/api/v1/descargas",
 "error_404_variable": "/api/v1/variables/no_existe",
 "error_404_datos": "/api/v1/series/lluvia_gpcp?region=noreste_mexico",
 "error_400_bbox": "/api/v1/series/lluvia_gpcp?oeste=-100",
 "error_422_param": "/api/v1/tendencias/lluvia_gpcp?alfa=0.9&sintetico=true",
}
for nombre, url in casos.items():
    r = c.get(url)
    try: body = r.json()
    except Exception: body = r.text
    (out/"ejemplos"/f"{nombre}.json").write_text(json.dumps({"request": f"GET {url}", "status": r.status_code, "response": body}, ensure_ascii=False, indent=2))
    print(f"{r.status_code}  {nombre:22s} {len(r.content):>9}B  {url}")
r = c.get(f"/demo/csv/anual?region=corredor_seco_centroamericano&{S}")
(out/"ejemplos"/"demo_csv_anual.csv").write_text(r.text); print(r.status_code, "csv", r.text[:300])
r = c.post("/api/v1/escaner", json={"region":"noreste_mexico","grupo":"lluvia","sintetico":True})
print("POST escaner", r.status_code)
r = c.post("/api/v1/dos-caras", json={"variable":"r20mm_imerg","variable_b":"cdd_imerg","region_a":"noreste_mexico","region_b":"noreste_mexico","sintetico":True})
(out/"ejemplos"/"dos_caras_post_variables.json").write_text(json.dumps({"request":"POST /api/v1/dos-caras","status":r.status_code,"response":r.json()}, ensure_ascii=False, indent=2)); print("POST dos-caras", r.status_code)
