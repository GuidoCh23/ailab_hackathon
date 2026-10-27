from functools import cache

from langchain_core.tools import tool

from catalogo.base_vectorial import buscar_en_coleccion
from conexiones.modelo_embeddings import crear_modelo_embeddings
from herramientas.catalogo_cargado import cargar_catalogo

# Debajo de esta similitud el resultado casi nunca tiene relacion con la pregunta
UMBRAL_DE_SIMILITUD = 0.6
CANTIDAD_DE_RESULTADOS = 5
# Que significa cada capa para quien usa el dato, solo adhoc es no oficial
ESTADO_POR_CAPA = {
    "powerbi": "oficial, dashboard publicado",
    "prod": "oficial, vista para reportes",
    "staging": "vista intermedia, valida para su tema",
    "raw": "datos de origen",
    "adhoc": "no oficial, creada por un analista",
}
# Ajuste al ordenar: las vistas oficiales suben y las de analistas bajan un poco
AJUSTE_POR_CAPA = {"prod": 0.03, "adhoc": -0.02}


@cache
def obtener_modelo_embeddings():
    return crear_modelo_embeddings()


def buscar_por_significado(nombre_coleccion, consulta):
    vector_consulta = obtener_modelo_embeddings().embed_query(consulta)
    encontrados = buscar_en_coleccion(nombre_coleccion, vector_consulta, CANTIDAD_DE_RESULTADOS)
    catalogo = cargar_catalogo()
    resultados = []
    for encontrado in encontrados:
        if encontrado["similitud"] < UMBRAL_DE_SIMILITUD:
            continue
        recurso = catalogo.get(encontrado["id"], {})
        resultado = {
            "nombre": encontrado["nombre"],
            "tipo": encontrado["tipo"],
            "capa": encontrado["capa"],
            "estado": ESTADO_POR_CAPA.get(encontrado["capa"], ""),
            "similitud": encontrado["similitud"],
            "puntaje": round(encontrado["similitud"] + AJUSTE_POR_CAPA.get(encontrado["capa"], 0), 3),
            "descripcion": recurso.get("descripcion", ""),
        }
        # Un dashboard ya dice que datos usa, sin tener que llamar a linaje
        if encontrado["tipo"] == "dashboard":
            resultado["titulo"] = recurso.get("titulo", "")
            resultado["datos_que_usa"] = [identificador.split(":", 1)[1] for identificador in recurso.get("lee_de", [])]
        resultados.append(resultado)
    if not resultados:
        return f"No se encontro nada parecido en {nombre_coleccion}."
    return sorted(resultados, key=lambda resultado: resultado["puntaje"], reverse=True)


@tool
def buscar_dashboards(consulta: str):
    """Busca dashboards de Power BI cuyo contenido se parece a la consulta. Usala cuando el usuario quiere
    hacer o encontrar un dashboard o reporte. Cada resultado trae su titulo y las vistas y tablas que usa."""
    return buscar_por_significado("dashboards", consulta)


@tool
def buscar_vistas(consulta: str):
    """Busca vistas de BigQuery cuyo contenido se parece a la consulta. Las vistas de la capa prod son las
    oficiales para reportes, las de adhoc no son oficiales."""
    return buscar_por_significado("vistas", consulta)


@tool
def buscar_tablas(consulta: str):
    """Busca tablas de BigQuery cuyo contenido se parece a la consulta. Las tablas estan en la capa raw y
    tienen los datos tal como llegan de los sistemas."""
    return buscar_por_significado("tablas", consulta)


@tool
def buscar_por_nombre(texto: str):
    """Busca recursos cuyo nombre contiene el texto, por ejemplo fct_revenue o v_revenue_snapshot. Usala
    cuando el usuario escribe el nombre de una tabla, vista o dashboard."""
    texto = texto.strip().strip("`").lower()
    resultados = [
        {"nombre": recurso["nombre"], "titulo": recurso.get("titulo", recurso["nombre"]),
         "tipo": recurso["tipo"], "capa": recurso["capa"]}
        for recurso in cargar_catalogo().values()
        if texto in recurso["nombre"].lower() or texto in recurso.get("titulo", "").lower()]
    return resultados if resultados else f"Ningun recurso tiene {texto} en su nombre."
