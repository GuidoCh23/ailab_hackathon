from langchain_core.tools import tool

from herramientas.catalogo_cargado import (buscar_fuentes, buscar_lectores, cargar_catalogo, encontrar_recurso,
                                          resumir_recurso)


def explicar_campo_de_dashboard(campo):
    # Agrega el significado de la columna para no confundir, por ejemplo, pais con unidad de negocio
    tabla, columna = campo.split(".", 1)
    significado = cargar_catalogo().get(f"tabla:raw.{tabla}", {}).get("significado_columnas", {}).get(columna)
    return f"raw.{campo}: {significado}" if significado else campo


def recorrer_niveles(identificador_inicial, buscar_siguientes):
    # Recorre el linaje nivel por nivel hasta que no haya mas recursos
    niveles = []
    actuales = [identificador_inicial]
    visitados = {identificador_inicial}
    while actuales:
        siguientes = []
        for identificador in actuales:
            for siguiente in buscar_siguientes(identificador):
                if siguiente not in visitados:
                    visitados.add(siguiente)
                    siguientes.append(siguiente)
        if siguientes:
            # El primer nivel es uso directo, los siguientes pasan por otros recursos
            relacion = "directa" if not niveles else "indirecta, a traves de los recursos del nivel anterior"
            niveles.append({"nivel": len(niveles) + 1, "relacion": relacion,
                            "recursos": [resumir_recurso(item) for item in siguientes]})
        actuales = siguientes
    return niveles


@tool
def obtener_ficha(nombre_recurso: str):
    """Devuelve la ficha de un dashboard, vista o tabla: descripcion, capa, ubicacion, columnas, de que lee,
    filas, ultima carga y sistemas de origen. En un dashboard tambien sus indicadores y filtros."""
    recurso = encontrar_recurso(nombre_recurso)
    if recurso is None:
        return f"No existe un recurso llamado {nombre_recurso}."
    ficha = {
        "nombre": recurso["nombre"],
        "tipo": recurso["tipo"],
        "capa": f"{recurso['capa']} ({recurso['descripcion_capa']})",
        "ubicacion": recurso["ubicacion"],
        "descripcion": recurso.get("descripcion", ""),
        "columnas": [columna["nombre"] for columna in recurso["columnas"]],
    }
    if recurso["tipo"] == "dashboard":
        ficha["titulo"] = recurso["titulo"]
        ficha["ubicacion"] = "Power BI web, en el link del dashboard"
        ficha["indicadores"] = recurso["medidas_usadas"]
        filtros = sorted({filtro for pagina in recurso["paginas"] for filtro in pagina["filtros"]})
        ficha["filtros"] = [explicar_campo_de_dashboard(filtro) for filtro in filtros]
        ficha["lee_de"] = [resumir_recurso(item) for item in recurso["lee_de"]]
    elif recurso["tipo"] == "vista":
        ficha["lee_de"] = [resumir_recurso(item) for item in recurso["lee_de"]]
    else:
        ficha["cantidad_filas"] = recurso["cantidad_filas"]
        ficha["ultima_carga"] = recurso["ultima_carga"]
        ficha["sistemas_origen"] = recurso["sistemas_origen"]
    return ficha


@tool
def obtener_origenes(nombre_recurso: str):
    """Devuelve de donde salen los datos de un recurso, nivel por nivel hasta las tablas de origen."""
    recurso = encontrar_recurso(nombre_recurso)
    if recurso is None:
        return f"No existe un recurso llamado {nombre_recurso}."
    niveles = recorrer_niveles(recurso["id"], buscar_fuentes)
    if not niveles:
        return f"{recurso['nombre']} no lee de ningun otro recurso, es una tabla de origen."
    return {"recurso": recurso["nombre"], "lee_de": niveles}


@tool
def obtener_dependientes(nombre_recurso: str):
    """Devuelve que vistas o dashboards usan este recurso, nivel por nivel. Sirve para saber a quien afecta
    un cambio."""
    recurso = encontrar_recurso(nombre_recurso)
    if recurso is None:
        return f"No existe un recurso llamado {nombre_recurso}."
    niveles = recorrer_niveles(recurso["id"], buscar_lectores)
    if not niveles:
        return f"Ningun recurso usa {recurso['nombre']}."
    return {"recurso": recurso["nombre"], "lo_usan": niveles}


@tool
def obtener_sql_de_vista(nombre_vista: str):
    """Devuelve el SQL con el que esta construida una vista, para ver filtros, uniones y calculos."""
    recurso = encontrar_recurso(nombre_vista)
    if recurso is None:
        return f"No existe un recurso llamado {nombre_vista}."
    if recurso["tipo"] != "vista":
        return f"{recurso['nombre']} es una {recurso['tipo']}, no tiene SQL."
    return recurso["sql"]
