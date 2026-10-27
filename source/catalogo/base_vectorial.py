import threading
import time
from functools import cache

import chromadb

from configuracion import CARPETA_CHROMA

# Una coleccion por tipo de recurso
COLECCION_POR_TIPO = {"dashboard": "dashboards", "vista": "vistas", "tabla": "tablas"}
CANTIDAD_DE_REINTENTOS = 3
# Evita que dos busquedas en paralelo abran Chroma al mismo tiempo
candado_chroma = threading.Lock()


@cache
def obtener_cliente_chroma():
    # Un solo cliente para todo el programa, abrir varios a la vez en paralelo falla
    return chromadb.PersistentClient(path=CARPETA_CHROMA)


def abrir_coleccion(nombre_coleccion):
    cliente_chroma = obtener_cliente_chroma()
    # Distancia coseno, la recomendada para embeddings de texto
    return cliente_chroma.get_or_create_collection(
        name=nombre_coleccion, configuration={"hnsw": {"space": "cosine"}})


def consultar_coleccion(nombre_coleccion, vector_pregunta, cantidad_resultados):
    with candado_chroma:
        coleccion = abrir_coleccion(nombre_coleccion)
        if coleccion.count() == 0:
            return None
        return coleccion.query(query_embeddings=[vector_pregunta],
                               n_results=min(cantidad_resultados, coleccion.count()))


def buscar_en_coleccion(nombre_coleccion, vector_pregunta, cantidad_resultados=5):
    # Si el archivo esta ocupado un momento, por ejemplo por OneDrive, se reintenta
    for intento in range(CANTIDAD_DE_REINTENTOS):
        try:
            resultado = consultar_coleccion(nombre_coleccion, vector_pregunta, cantidad_resultados)
            break
        except Exception:
            if intento == CANTIDAD_DE_REINTENTOS - 1:
                raise
            time.sleep(1)
    if resultado is None:
        return []
    encontrados = []
    for identificador, distancia, metadatos in zip(
            resultado["ids"][0], resultado["distances"][0], resultado["metadatas"][0]):
        # Similitud de 0 a 1, mas alto es mas parecido
        encontrados.append({"id": identificador, "similitud": round(1 - distancia, 3), **metadatos})
    return encontrados
