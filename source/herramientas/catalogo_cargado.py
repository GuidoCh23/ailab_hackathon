import os
from functools import cache

from catalogo.archivos_catalogo import leer_descripciones, leer_json, leer_todos_los_recursos
from configuracion import RUTA_PERFIL_COLUMNAS, RUTA_SIGNIFICADO_COLUMNAS


def leer_si_existe(ruta_archivo):
    return leer_json(ruta_archivo) if os.path.exists(ruta_archivo) else {}


@cache
def cargar_catalogo():
    # Junta en un solo diccionario todo lo que se sabe de cada recurso
    descripciones = leer_descripciones()
    perfiles = leer_si_existe(RUTA_PERFIL_COLUMNAS)
    significados = leer_si_existe(RUTA_SIGNIFICADO_COLUMNAS)
    catalogo = {}
    for recurso in leer_todos_los_recursos():
        identificador = recurso["id"]
        catalogo[identificador] = {
            **recurso,
            **descripciones.get(identificador, {}),
            "perfil_columnas": perfiles.get(identificador, []),
            "significado_columnas": significados.get(identificador, {}),
        }
    return catalogo


def encontrar_recurso(nombre):
    # Acepta el id, el nombre con dataset, solo el nombre del objeto o el titulo del dashboard
    nombre = nombre.strip().strip("`").lower()
    for recurso in cargar_catalogo().values():
        nombres_posibles = [recurso["id"].lower(), recurso["nombre"].lower(), recurso["nombre"].split(".")[-1].lower(),
                            recurso.get("titulo", "").lower()]
        if nombre in nombres_posibles:
            return recurso
    return None


def buscar_lectores(identificador):
    # Los recursos que leen de este, es decir sus dependientes
    return [recurso["id"] for recurso in cargar_catalogo().values() if identificador in recurso.get("lee_de", [])]


def buscar_fuentes(identificador):
    recurso = cargar_catalogo().get(identificador, {})
    return recurso.get("lee_de", [])


def resumir_recurso(identificador):
    recurso = cargar_catalogo().get(identificador)
    if recurso is None:
        return {"id": identificador}
    resumen = {"nombre": recurso["nombre"], "tipo": recurso["tipo"], "capa": recurso["capa"]}
    if recurso["tipo"] == "dashboard":
        resumen["titulo"] = recurso["titulo"]
    return resumen
