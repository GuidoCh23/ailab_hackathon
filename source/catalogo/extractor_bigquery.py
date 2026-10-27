import re

from catalogo.archivos_catalogo import guardar_json
from conexiones.cliente_bigquery import crear_cliente_bigquery, ejecutar_consulta
from configuracion import BIGQUERY_UBICACION, GCP_PROYECTO, RUTA_PERFIL_COLUMNAS, RUTA_RECURSOS_BIGQUERY

DATASETS_DEL_CATALOGO = ["raw", "staging", "prod", "adhoc"]

DESCRIPCION_DE_CAPAS = {
    "raw": "datos tal como llegan de los sistemas y archivos manuales",
    "staging": "vistas intermedias con renombres y cortes por region",
    "prod": "vistas oficiales que consumen los reportes",
    "adhoc": "vistas creadas por analistas, no oficiales",
}

# Columnas que dicen de que sistema o archivo viene cada fila
COLUMNAS_DE_ORIGEN = ["source_system", "SRC_FILENAME"]

# Hasta esta cantidad de valores distintos una columna se trata como categoria
MAXIMO_VALORES_DE_CATEGORIA = 30
TIPOS_NUMERICOS = ["NUMERIC", "BIGNUMERIC", "FLOAT64"]
TIPOS_FECHA = ["DATE", "DATETIME", "TIMESTAMP", "TIME"]

ESQUEMA_INFORMACION = f"`{GCP_PROYECTO}.region-{BIGQUERY_UBICACION.lower()}.INFORMATION_SCHEMA`"


def crear_link_consola(dataset, nombre_objeto):
    return (
        f"https://console.cloud.google.com/bigquery?project={GCP_PROYECTO}"
        f"&ws=!1m5!1m4!4m3!1s{GCP_PROYECTO}!2s{dataset}!3s{nombre_objeto}"
    )


def leer_objetos():
    consulta_sql = f"""
    SELECT table_schema AS dataset, table_name AS nombre_objeto, table_type AS tipo_objeto
    FROM {ESQUEMA_INFORMACION}.TABLES
    ORDER BY dataset, nombre_objeto
    """
    objetos = ejecutar_consulta(consulta_sql)
    return objetos[objetos["dataset"].isin(DATASETS_DEL_CATALOGO)]


def leer_columnas():
    consulta_sql = f"""
    SELECT table_schema AS dataset, table_name AS nombre_objeto, column_name AS columna, data_type AS tipo_dato
    FROM {ESQUEMA_INFORMACION}.COLUMNS
    ORDER BY dataset, nombre_objeto, ordinal_position
    """
    columnas_por_objeto = {}
    for fila in ejecutar_consulta(consulta_sql).itertuples():
        clave = f"{fila.dataset}.{fila.nombre_objeto}"
        columnas_por_objeto.setdefault(clave, []).append({"nombre": fila.columna, "tipo": fila.tipo_dato})
    return columnas_por_objeto


def leer_sql_de_vistas():
    consulta_sql = f"""
    SELECT table_schema AS dataset, table_name AS nombre_objeto, view_definition AS sql_vista
    FROM {ESQUEMA_INFORMACION}.VIEWS
    """
    return {f"{fila.dataset}.{fila.nombre_objeto}": fila.sql_vista
            for fila in ejecutar_consulta(consulta_sql).itertuples()}


def encontrar_objetos_leidos(sql_vista):
    # Busca referencias del tipo `proyecto.dataset.objeto` dentro del SQL
    referencias = re.findall(r"`[^`]+\.(\w+)\.(\w+)`", sql_vista)
    return sorted({f"{dataset}.{nombre_objeto}" for dataset, nombre_objeto in referencias})


def leer_ultima_carga_y_origen(dataset, nombre_tabla, nombres_columnas):
    columna_carga = next((columna for columna in nombres_columnas if columna.lower().startswith("bq_ingest")), None)
    columna_origen = next((columna for columna in COLUMNAS_DE_ORIGEN if columna in nombres_columnas), None)

    partes_select = []
    if columna_carga:
        partes_select.append(f"CAST(MAX({columna_carga}) AS STRING) AS ultima_carga")
    if columna_origen:
        partes_select.append(f"ARRAY_AGG(DISTINCT {columna_origen} IGNORE NULLS) AS sistemas_origen")
    if not partes_select:
        return None, []

    consulta_sql = f"SELECT {', '.join(partes_select)} FROM `{GCP_PROYECTO}.{dataset}.{nombre_tabla}`"
    resultado = ejecutar_consulta(consulta_sql).iloc[0]
    ultima_carga = resultado["ultima_carga"] if columna_carga else None
    sistemas_origen = sorted(resultado["sistemas_origen"]) if columna_origen else []
    return ultima_carga, sistemas_origen


def clasificar_columna(columna, cantidad_valores_distintos):
    if columna["tipo"] in TIPOS_NUMERICOS:
        return "medida"
    if columna["tipo"] in TIPOS_FECHA:
        return "fecha"
    if "uuid" in columna["nombre"].lower() or cantidad_valores_distintos > MAXIMO_VALORES_DE_CATEGORIA:
        return "unico"
    return "categoria"


def leer_perfil_de_columnas(dataset, nombre_tabla, columnas):
    # Una sola consulta cuenta los valores distintos de cada columna y trae los primeros
    partes_select = []
    for posicion, columna in enumerate(columnas):
        valor_en_texto = f"CAST(`{columna['nombre']}` AS STRING)"
        partes_select.append(f"COUNT(DISTINCT {valor_en_texto}) AS cantidad_{posicion}")
        partes_select.append(
            f"ARRAY_AGG(DISTINCT {valor_en_texto} IGNORE NULLS ORDER BY {valor_en_texto} "
            f"LIMIT {MAXIMO_VALORES_DE_CATEGORIA + 1}) AS valores_{posicion}")
    consulta_sql = f"SELECT {', '.join(partes_select)} FROM `{GCP_PROYECTO}.{dataset}.{nombre_tabla}`"
    resultado = ejecutar_consulta(consulta_sql).iloc[0]

    perfil = []
    for posicion, columna in enumerate(columnas):
        cantidad_valores_distintos = int(resultado[f"cantidad_{posicion}"])
        tipo_de_contenido = clasificar_columna(columna, cantidad_valores_distintos)
        perfil.append({
            "nombre": columna["nombre"],
            "tipo_de_contenido": tipo_de_contenido,
            "cantidad_valores_distintos": cantidad_valores_distintos,
            # Solo las categorias guardan sus valores, nunca datos unicos o personales
            "valores": list(resultado[f"valores_{posicion}"]) if tipo_de_contenido == "categoria" else [],
        })
    return perfil


def extraer_catalogo():
    cliente = crear_cliente_bigquery()
    objetos = leer_objetos()
    columnas_por_objeto = leer_columnas()
    sql_por_vista = leer_sql_de_vistas()

    recursos = []
    perfil_por_recurso = {}
    for objeto in objetos.itertuples():
        nombre_completo = f"{objeto.dataset}.{objeto.nombre_objeto}"
        columnas = columnas_por_objeto.get(nombre_completo, [])
        es_vista = objeto.tipo_objeto == "VIEW"

        recurso = {
            "id": f"{'vista' if es_vista else 'tabla'}:{nombre_completo}",
            "tipo": "vista" if es_vista else "tabla",
            "nombre": nombre_completo,
            "capa": objeto.dataset,
            "descripcion_capa": DESCRIPCION_DE_CAPAS[objeto.dataset],
            "ubicacion": f"{GCP_PROYECTO}.{nombre_completo}",
            "link": crear_link_consola(objeto.dataset, objeto.nombre_objeto),
            "columnas": columnas,
        }
        # Tablas y vistas guardan el perfil de sus columnas en extras
        perfil_por_recurso[recurso["id"]] = leer_perfil_de_columnas(objeto.dataset, objeto.nombre_objeto, columnas)

        if es_vista:
            sql_vista = sql_por_vista[nombre_completo]
            recurso["sql"] = sql_vista
            recurso["lee_de"] = [f"{'vista' if leido in sql_por_vista else 'tabla'}:{leido}"
                                 for leido in encontrar_objetos_leidos(sql_vista)]
        else:
            nombres_columnas = [columna["nombre"] for columna in columnas]
            ultima_carga, sistemas_origen = leer_ultima_carga_y_origen(
                objeto.dataset, objeto.nombre_objeto, nombres_columnas)
            recurso["cantidad_filas"] = cliente.get_table(f"{GCP_PROYECTO}.{nombre_completo}").num_rows
            recurso["ultima_carga"] = ultima_carga
            recurso["sistemas_origen"] = sistemas_origen

        recursos.append(recurso)
        print(f"{recurso['tipo']:<6} {nombre_completo}")

    guardar_json(RUTA_RECURSOS_BIGQUERY, recursos)
    guardar_json(RUTA_PERFIL_COLUMNAS, perfil_por_recurso)
    print(f"\nGuardados {len(recursos)} recursos en {RUTA_RECURSOS_BIGQUERY}")


if __name__ == "__main__":
    extraer_catalogo()
