import re
from functools import cache

from herramientas.catalogo_cargado import cargar_catalogo
from herramientas.herramientas_detalle import normalizar

MAXIMO_RECURSOS_CON_COLUMNAS = 6
# Palabras de SQL o comunes que pueden aparecer en un filtro y no son columnas
PALABRAS_PERMITIDAS = {"select", "from", "where", "and", "or", "not", "in", "is", "null", "sum", "count", "group",
                       "by", "order", "as", "join", "on", "left", "true", "false", "case", "when", "then", "else",
                       "end", "distinct", "max", "min", "avg", "like", "between", "having", "limit", "t", "f",
                       "raw", "staging", "prod", "adhoc", "powerbi", "usd"}


@cache
def leer_nombres_y_valores():
    # Todos los nombres que existen en el catalogo y los valores reales de cada columna de categoria
    nombres_conocidos = set(PALABRAS_PERMITIDAS)
    valores_por_columna = {}
    for recurso in cargar_catalogo().values():
        nombres_conocidos.add(recurso["nombre"].split(".")[-1].lower())
        for columna in recurso.get("columnas", []):
            nombres_conocidos.add(columna["nombre"].lower())
        for columna in recurso.get("perfil_columnas", []):
            if columna["tipo_de_contenido"] == "categoria":
                # Valor normalizado para comparar y valor original para mostrar
                valores = valores_por_columna.setdefault(columna["nombre"].lower(), {})
                valores.update({normalizar(valor): valor for valor in columna["valores"]})
    todos_los_valores = {valor for valores in valores_por_columna.values() for valor in valores}
    return nombres_conocidos, valores_por_columna, todos_los_valores


def listar_columnas_de_recursos(texto):
    # Columnas reales de las tablas y vistas nombradas en el texto, para que el redactor no las adivine
    lineas = []
    for recurso in cargar_catalogo().values():
        if recurso["tipo"] == "dashboard" or not re.search(rf"\b{re.escape(recurso['nombre'])}\b", texto):
            continue
        nombres = ", ".join(columna["nombre"] for columna in recurso["columnas"])
        lineas.append(f"{recurso['nombre']}: {nombres}")
        if len(lineas) >= MAXIMO_RECURSOS_CON_COLUMNAS:
            break
    if not lineas:
        return ""
    return "\n\nColumnas reales de los recursos mencionados (usa solo estas en filtros):\n" + "\n".join(lineas)


def encontrar_columnas_inventadas(respuesta):
    nombres_conocidos, valores_por_columna, todos_los_valores = leer_nombres_y_valores()
    problemas = []
    # Filtros del tipo columna = 'valor' o columna = VALOR, y uniones del tipo columna = otra_columna
    patron = r"`?\b([A-Za-z_]\w*)`?\s*(?:=|<>|!=)\s*`?('?)([A-Za-z0-9_][\w &-]*?)\2`?(?=[`\s,;)]|$)"
    for columna, comilla, valor in re.findall(patron, respuesta):
        nombre = columna.lower()
        otra_columna = valor.lower()
        if nombre not in nombres_conocidos:
            problemas.append(f"la columna {columna} no existe")
        elif not comilla and otra_columna in valores_por_columna and nombre in valores_por_columna:
            # Una union entre columnas solo sirve si comparten valores
            if not set(valores_por_columna[nombre]) & set(valores_por_columna[otra_columna]):
                ejemplo_uno = ", ".join(sorted(valores_por_columna[nombre].values())[:4])
                ejemplo_dos = ", ".join(sorted(valores_por_columna[otra_columna].values())[:4])
                problemas.append(f"la union {columna} = {valor} no coincide: {columna} tiene valores como "
                                 f"{ejemplo_uno} y {valor} tiene valores como {ejemplo_dos}")
        elif not comilla and (otra_columna in nombres_conocidos or valor.isalpha() and valor.islower()):
            # Otra columna sin valores para comparar, o texto corrido como "escenario = el que quieras"
            continue
        elif nombre in valores_por_columna and normalizar(valor) not in valores_por_columna[nombre]:
            reales = ", ".join(sorted(valores_por_columna[nombre].values())[:12])
            problemas.append(f"el valor {valor} no existe en la columna {columna}, sus valores reales son: {reales}")
    # Nombres sueltos entre comillas invertidas
    for identificador in re.findall(r"`([A-Za-z_]\w*)`", respuesta):
        nombre = identificador.lower()
        if nombre not in nombres_conocidos and normalizar(identificador) not in todos_los_valores:
            problemas.append(f"la columna {identificador} no existe")
    return sorted(set(problemas))
