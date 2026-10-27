import unicodedata

from langchain_core.tools import tool

from herramientas.catalogo_cargado import cargar_catalogo, encontrar_recurso

MAXIMO_COINCIDENCIAS = 25

TEXTO_POR_CONTENIDO = {
    "unico": "valores unicos, identificador o dato personal, no se listan",
    "medida": "monto o medida numerica",
    "fecha": "fecha o momento de carga",
}


def normalizar(texto):
    # Minusculas y sin tildes para comparar textos escritos de distinta forma
    texto = unicodedata.normalize("NFKD", str(texto).lower())
    return "".join(caracter for caracter in texto if not unicodedata.combining(caracter))


def detectar_valores_mencionados(texto):
    # Un valor cuenta como mencionado si todas sus palabras estan en el texto
    palabras = set(normalizar(texto).replace("?", " ").replace(",", " ").split())
    encontrados = []
    for recurso in cargar_catalogo().values():
        for columna in recurso["perfil_columnas"]:
            for valor in columna["valores"]:
                palabras_del_valor = set(normalizar(valor).split())
                if len(normalizar(valor)) >= 4 and palabras_del_valor <= palabras:
                    encontrados.append(f"{valor} en {recurso['nombre']}.{columna['nombre']}")
    return encontrados[:MAXIMO_COINCIDENCIAS]


@tool
def obtener_columnas(nombre_recurso: str, filtro: str = ""):
    """Devuelve las columnas de una tabla o vista con su significado y, si es una categoria, sus valores reales.
    Usa filtro con una palabra (por ejemplo pais, canal o escenario) para traer solo las columnas que la
    mencionan en su nombre, significado o valores. Sin filtro trae todas."""
    recurso = encontrar_recurso(nombre_recurso)
    if recurso is None:
        return f"No existe un recurso llamado {nombre_recurso}."
    texto_filtro = normalizar(filtro)
    columnas = []
    for columna in recurso["perfil_columnas"]:
        significado = recurso["significado_columnas"].get(columna["nombre"], "")
        # Con filtro solo quedan las columnas relacionadas, para no mandar texto de mas al modelo
        texto_de_columna = normalizar(" ".join([columna["nombre"], significado] + columna["valores"]))
        if texto_filtro and texto_filtro not in texto_de_columna:
            continue
        if columna["tipo_de_contenido"] == "categoria":
            contenido = {"valores": columna["valores"]}
        else:
            contenido = {"contenido": TEXTO_POR_CONTENIDO[columna["tipo_de_contenido"]]}
        columnas.append({"columna": columna["nombre"], "significado": significado, **contenido})
    if not columnas:
        return f"Ninguna columna de {recurso['nombre']} menciona {filtro}."
    return {"recurso": recurso["nombre"], "capa": recurso["capa"], "columnas": columnas}


@tool
def buscar_valor(texto: str):
    """Busca en que tablas y vistas aparece un valor de categoria (por ejemplo TRADICIONAL, PEN o Supermercados)
    o una columna con ese nombre. Usala cuando el usuario menciona un atributo especifico."""
    texto_buscado = normalizar(texto)
    coincidencias = []
    for recurso in cargar_catalogo().values():
        for columna in recurso["perfil_columnas"]:
            valores_encontrados = [valor for valor in columna["valores"] if texto_buscado in normalizar(valor)]
            nombre_coincide = texto_buscado in normalizar(columna["nombre"])
            if valores_encontrados or nombre_coincide:
                coincidencias.append({
                    "recurso": recurso["nombre"],
                    "capa": recurso["capa"],
                    "columna": columna["nombre"],
                    "valores_encontrados": valores_encontrados,
                })
    if not coincidencias:
        return f"Ninguna columna ni valor de categoria contiene {texto}."
    # Primero las vistas oficiales, luego el resto
    coincidencias.sort(key=lambda coincidencia: coincidencia["capa"] != "prod")
    return coincidencias[:MAXIMO_COINCIDENCIAS]
