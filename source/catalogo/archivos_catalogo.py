import glob
import json
import os

from configuracion import CARPETA_DESCRIPCIONES, RUTA_RECURSOS_BIGQUERY, RUTA_RECURSOS_DASHBOARDS


def guardar_json(ruta_archivo, contenido):
    os.makedirs(os.path.dirname(ruta_archivo), exist_ok=True)
    with open(ruta_archivo, "w", encoding="utf-8") as archivo:
        json.dump(contenido, archivo, indent=2, ensure_ascii=False, default=str)


def leer_json(ruta_archivo):
    with open(ruta_archivo, encoding="utf-8") as archivo:
        return json.load(archivo)


def leer_todos_los_recursos():
    # Primero los dashboards, que son lo que mas se pregunta
    dashboards = leer_json(RUTA_RECURSOS_DASHBOARDS) if os.path.exists(RUTA_RECURSOS_DASHBOARDS) else []
    return dashboards + leer_json(RUTA_RECURSOS_BIGQUERY)


def leer_descripciones():
    # Junta los archivos de descripciones escritas a mano: dashboards, vistas y tablas
    descripciones = {}
    for ruta_archivo in sorted(glob.glob(os.path.join(CARPETA_DESCRIPCIONES, "*.json"))):
        descripciones.update(leer_json(ruta_archivo))
    return descripciones
