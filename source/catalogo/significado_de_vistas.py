import re

from catalogo.archivos_catalogo import guardar_json, leer_json
from configuracion import RUTA_RECURSOS_BIGQUERY, RUTA_SIGNIFICADO_COLUMNAS


def leer_tablas_del_sql(sql_vista):
    # Relaciona cada alias del SQL con su tabla, por ejemplo f con raw.fct_revenue
    alias_por_tabla = re.findall(r"`[^`]+\.(\w+)\.(\w+)`\s+(?:AS\s+)?(\w+)", sql_vista, re.IGNORECASE)
    return {alias: f"tabla:{dataset}.{tabla}" for dataset, tabla, alias in alias_por_tabla}


def heredar_significados(vista, significados):
    sql_vista = vista["sql"]
    tabla_por_alias = leer_tablas_del_sql(sql_vista)
    heredados = {}
    # Una vista que copia todas las columnas de su tabla hereda todo
    copia_completa = re.search(r"SELECT\s+(\w+)\.\*", sql_vista, re.IGNORECASE)
    if copia_completa:
        return dict(significados.get(tabla_por_alias.get(copia_completa.group(1)), {}))
    # Columnas del tipo alias.columna o alias.columna AS nuevo_nombre
    for alias, columna, nuevo_nombre in re.findall(r"\b(\w+)\.(\w+)(?:\s+AS\s+`?(\w+)`?)?", sql_vista, re.IGNORECASE):
        significado = significados.get(tabla_por_alias.get(alias), {}).get(columna)
        if significado:
            heredados.setdefault(nuevo_nombre or columna, significado)
    nombres_de_columnas = {columna["nombre"] for columna in vista["columnas"]}
    return {columna: significado for columna, significado in heredados.items() if columna in nombres_de_columnas}


def completar_significados_de_vistas():
    significados = leer_json(RUTA_SIGNIFICADO_COLUMNAS)
    for recurso in leer_json(RUTA_RECURSOS_BIGQUERY):
        if recurso["tipo"] != "vista":
            continue
        heredados = heredar_significados(recurso, significados)
        significados[recurso["id"]] = heredados
        print(f"{recurso['nombre']}: {len(heredados)} de {len(recurso['columnas'])} columnas")
    guardar_json(RUTA_SIGNIFICADO_COLUMNAS, significados)


if __name__ == "__main__":
    completar_significados_de_vistas()
