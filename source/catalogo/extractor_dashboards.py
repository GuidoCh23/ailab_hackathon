import glob
import json
import os
import re
import zipfile

from pbixray import PBIXRay

from catalogo.archivos_catalogo import guardar_json, leer_json
from configuracion import (CARPETA_DASHBOARDS, CARPETA_PROYECTO, RUTA_LINKS_DASHBOARDS, RUTA_MEDIDAS_DASHBOARDS,
                           RUTA_RECURSOS_BIGQUERY, RUTA_RECURSOS_DASHBOARDS)

# Graficos que solo decoran la pagina
TIPOS_DECORATIVOS = ["shape", "image", "actionButton"]


def buscar_campos(nodo, campos):
    # Recorre el json de un grafico y junta las columnas y medidas que usa
    if isinstance(nodo, dict):
        for tipo_de_campo in ["Column", "Measure", "HierarchyLevel"]:
            campo = nodo.get(tipo_de_campo)
            if isinstance(campo, dict):
                tabla = campo.get("Expression", {}).get("SourceRef", {}).get("Entity")
                nombre = campo.get("Property") or campo.get("Level")
                if tabla and nombre:
                    campos.add(("medida" if tipo_de_campo == "Measure" else "columna", tabla, nombre))
        for valor in nodo.values():
            buscar_campos(valor, campos)
    elif isinstance(nodo, list):
        for valor in nodo:
            buscar_campos(valor, campos)


def leer_texto_literal(propiedad):
    valor = propiedad.get("expr", {}).get("Literal", {}).get("Value", "")
    return valor.strip("'")


def leer_textos_de_grafico(grafico):
    # Titulo del grafico y texto de los cuadros de texto
    textos = []
    for titulo in grafico.get("visualContainerObjects", {}).get("title", []):
        texto = leer_texto_literal(titulo.get("properties", {}).get("text", {}))
        if texto:
            textos.append(texto)
    for general in grafico.get("visual", {}).get("objects", {}).get("general", []):
        for parrafo in general.get("properties", {}).get("paragraphs", []):
            texto = "".join(corrida.get("value", "") for corrida in parrafo.get("textRuns", []))
            if texto.strip():
                textos.append(texto.strip())
    return textos


def leer_paginas(archivo_pbix):
    paginas = {}
    for ruta_interna in sorted(archivo_pbix.namelist()):
        partes = ruta_interna.split("/")
        if ruta_interna.endswith("page.json"):
            pagina = json.loads(archivo_pbix.read(ruta_interna))
            paginas.setdefault(partes[-2], {"textos": [], "graficos": [], "filtros": []})["nombre"] = pagina["displayName"]
        elif ruta_interna.endswith("visual.json"):
            pagina = paginas.setdefault(partes[-4], {"textos": [], "graficos": [], "filtros": []})
            grafico = json.loads(archivo_pbix.read(ruta_interna))
            tipo_de_grafico = grafico.get("visual", {}).get("visualType", "grupo")
            if tipo_de_grafico in TIPOS_DECORATIVOS:
                continue
            pagina["textos"] += leer_textos_de_grafico(grafico)
            campos = set()
            buscar_campos(grafico.get("visual", {}).get("query", {}), campos)
            if not campos:
                continue
            campos_ordenados = sorted(campos)
            if tipo_de_grafico == "slicer":
                pagina["filtros"] += [f"{tabla}.{nombre}" for _, tabla, nombre in campos_ordenados]
            else:
                pagina["graficos"].append({"tipo": tipo_de_grafico, "campos": campos_ordenados})
    return list(paginas.values())


def leer_origen_en_bigquery(expresion_power_query):
    # El Power Query dice de que dataset y tabla o vista de BigQuery sale cada tabla del modelo
    dataset = re.search(r'Name="(\w+)",Kind="Schema"', expresion_power_query)
    objeto = re.search(r'Name="(\w+)",Kind="(Table|View)"', expresion_power_query)
    if not dataset or not objeto:
        return None
    tipo = "vista" if objeto.group(2) == "View" else "tabla"
    return f"{tipo}:{dataset.group(1)}.{objeto.group(1)}"


def buscar_referencias_dax(expresion, nombres_de_medidas):
    tablas = set(re.findall(r"'([^']+)'\[", expresion)) | set(re.findall(r"(\w+)\[", expresion))
    medidas = {nombre for nombre in re.findall(r"(?<![\w'])\[([^\]]+)\]", expresion) if nombre in nombres_de_medidas}
    return tablas, medidas


def calcular_tablas_usadas(paginas, formulas_de_medidas, formulas_de_tablas_calculadas):
    tablas_usadas = set()
    medidas_pendientes = []
    for pagina in paginas:
        campos = [campo for grafico in pagina["graficos"] for campo in grafico["campos"]]
        campos += [("columna", *filtro.split(".", 1)) for filtro in pagina["filtros"]]
        for tipo_de_campo, tabla, nombre in campos:
            if tipo_de_campo == "medida":
                medidas_pendientes.append(nombre)
            else:
                tablas_usadas.add(tabla)
    # Sigue las medidas que llaman a otras medidas
    medidas_revisadas = set()
    while medidas_pendientes:
        medida = medidas_pendientes.pop()
        if medida in medidas_revisadas or medida not in formulas_de_medidas:
            continue
        medidas_revisadas.add(medida)
        tablas, medidas = buscar_referencias_dax(formulas_de_medidas[medida], formulas_de_medidas)
        tablas_usadas |= tablas
        medidas_pendientes += list(medidas)
    # Las tablas calculadas dentro de Power BI salen de otras tablas del modelo
    for tabla_calculada, formula in formulas_de_tablas_calculadas.items():
        if tabla_calculada in tablas_usadas:
            tablas_usadas |= buscar_referencias_dax(formula, {})[0]
    return tablas_usadas, sorted(medidas_revisadas)


def extraer_dashboard(ruta_pbix, links, identificadores_bigquery):
    nombre_archivo = os.path.splitext(os.path.basename(ruta_pbix))[0]
    with zipfile.ZipFile(ruta_pbix) as archivo_pbix:
        paginas = leer_paginas(archivo_pbix)

    modelo = PBIXRay(ruta_pbix)
    origen_por_tabla = {fila.TableName: leer_origen_en_bigquery(fila.Expression)
                        for fila in modelo.power_query.itertuples()}
    formulas_de_medidas = {fila.Name: fila.Expression for fila in modelo.dax_measures.itertuples()}
    formulas_de_tablas_calculadas = {fila.TableName: fila.Expression for fila in modelo.dax_tables.itertuples()}

    tablas_usadas, medidas_usadas = calcular_tablas_usadas(paginas, formulas_de_medidas, formulas_de_tablas_calculadas)
    lee_de = sorted({origen_por_tabla[tabla] for tabla in tablas_usadas
                     if origen_por_tabla.get(tabla) in identificadores_bigquery})
    modelo_carga = sorted({origen for origen in origen_por_tabla.values() if origen in identificadores_bigquery})

    recurso = {
        "id": f"dashboard:powerbi.{nombre_archivo.lower()}",
        "tipo": "dashboard",
        "nombre": f"powerbi.{nombre_archivo.lower()}",
        "titulo": " | ".join(pagina["nombre"] for pagina in paginas),
        "capa": "powerbi",
        "descripcion_capa": "dashboards de Power BI que consumen los usuarios",
        "ubicacion": os.path.relpath(ruta_pbix, CARPETA_PROYECTO),
        "link": links.get(nombre_archivo, ""),
        "paginas": paginas,
        "medidas_usadas": medidas_usadas,
        "lee_de": lee_de,
        "modelo_carga": modelo_carga,
        "columnas": [],
    }
    medidas = [{"nombre": nombre, "formula": formula} for nombre, formula in formulas_de_medidas.items()]
    return recurso, medidas


def extraer_dashboards():
    links = leer_json(RUTA_LINKS_DASHBOARDS) if os.path.exists(RUTA_LINKS_DASHBOARDS) else {}
    identificadores_bigquery = {recurso["id"] for recurso in leer_json(RUTA_RECURSOS_BIGQUERY)}
    recursos = []
    medidas_por_dashboard = {}
    for ruta_pbix in sorted(glob.glob(os.path.join(CARPETA_DASHBOARDS, "*.pbix"))):
        recurso, medidas = extraer_dashboard(ruta_pbix, links, identificadores_bigquery)
        recursos.append(recurso)
        medidas_por_dashboard[recurso["id"]] = medidas
        print(f"{recurso['nombre']}: lee de {len(recurso['lee_de'])} recursos, link {'si' if recurso['link'] else 'no'}")

    guardar_json(RUTA_RECURSOS_DASHBOARDS, recursos)
    # Las formulas de las medidas quedan en extras, no van a la descripcion
    guardar_json(RUTA_MEDIDAS_DASHBOARDS, medidas_por_dashboard)
    print(f"\nGuardados {len(recursos)} dashboards en {RUTA_RECURSOS_DASHBOARDS}")


if __name__ == "__main__":
    extraer_dashboards()
