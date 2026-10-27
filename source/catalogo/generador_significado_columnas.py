import json
import os
import re

from pydantic import BaseModel, Field

from catalogo.archivos_catalogo import guardar_json, leer_json
from conexiones.modelo_groq import crear_modelo_potente
from configuracion import RUTA_PERFIL_COLUMNAS, RUTA_RECURSOS_BIGQUERY, RUTA_SIGNIFICADO_COLUMNAS

CONTEXTO_DE_NEGOCIO = """
Empresa ficticia Sabora, modelo de ventas (Revenue) de LATAM.
Capas en BigQuery: raw (datos de origen), staging (vistas intermedias y cortes por region),
prod (vistas oficiales para reportes), adhoc (vistas de analistas, no oficiales).
Escenarios: AC real, PY real del anio anterior, BU presupuesto, JF SF LF forecasts de junio, septiembre y ultimo.
Montos: amount_lc moneda local del pais, amount_rc USD a la tasa del escenario,
amount_ac USD a tasa real, amount_py USD a tasa del anio anterior.
Regiones: BRAZIL, MEXICO, SOCO (cono sur), WACAM (andina y centroamerica), HQ LATAM.
Escenarios de forecast: JF es el forecast de junio, SF el de septiembre y LF el ultimo forecast.
Archivo manual BE (manual_be_hq_latam): Best Estimate manual de HQ LATAM, en miles de USD
(la cuenta VOLUME_TON en toneladas). MV_3 es el ciclo de forecast SF y MV_2 el ciclo JF.
El sufijo _at_X indica la tasa de cambio del monto: RPT tasa de reporte, AC tasa real, PY tasa del anio anterior,
SF tasa del forecast de septiembre, LF tasa del ultimo forecast, AC_next_year tasa del anio siguiente.
RF es la ronda de forecast. AC_at_PY es el real a tasa del anio anterior.
Archivos de stock (stock_os_si_so y stock_mv_si_so): SI es sell-in (venta a clientes), SO es sell-out
(venta del cliente al consumidor), STOCK_CANAL es el inventario en el canal y DIAS_INVENTARIO los dias de inventario,
del canal tradicional por entidad, categoria y mes. stock_os esta en USD completos, stock_mv en miles de USD.
NR es Net Revenue (venta neta). Gross to Net es el paso de venta bruta a venta neta: descuentos, trade spend
y devoluciones. BU es unidad de negocio (las regiones) y tambien presupuesto segun el contexto.
"""

INSTRUCCIONES = """
Eres un documentador de datos. Para la tabla o vista de BigQuery que recibes, explica en espanol que significa
cada columna en lenguaje de negocio, una oracion por columna, sin saltarte ninguna y con su nombre exacto.
Cada columna trae su contenido: categoria (con la lista completa de valores reales),
unico (identificadores, nombres o datos personales), medida (montos) o fecha.
En el significado NO escribas valores ni ejemplos, los valores reales se guardan aparte.
Las columnas que empiezan con dimid_ en una tabla de hechos son claves que unen con una tabla dim_:
describelas como la clave hacia esa dimension, sin adivinar que contiene.
Si es una vista, usa su SQL para explicar de donde sale cada columna y si se calcula o filtra.
Nunca inventes valores, categorias ni datos que no esten en los metadatos.
"""


class ColumnaExplicada(BaseModel):
    columna: str = Field(description="nombre exacto de la columna")
    significado: str = Field(description="que significa en lenguaje de negocio, una oracion, sin ejemplos")


class SignificadoDeColumnas(BaseModel):
    columnas_explicadas: list[ColumnaExplicada] = Field(description="una entrada por cada columna")


def quitar_ejemplos(significado):
    # Ultima defensa: borra cualquier ejemplo que el modelo haya escrito igual
    significado = re.sub(r"\s*\((por ejemplo|p\. ?ej\.|ej\.)[^)]*\)", "", significado, flags=re.IGNORECASE)
    significado = re.sub(r",?\s*(por ejemplo|p\. ?ej\.)[^.]*", "", significado, flags=re.IGNORECASE)
    return significado.strip()


def encontrar_problemas(perfil, resultado):
    explicadas = {columna.columna for columna in resultado.columnas_explicadas}
    problemas = [f"falta explicar {columna['nombre']}" for columna in perfil if columna["nombre"] not in explicadas]
    # Los ejemplos en el significado suelen ser inventados
    problemas += [f"quita los ejemplos de {columna.columna}"
                  for columna in resultado.columnas_explicadas
                  if "ejemplo" in columna.significado.lower() or "ej." in columna.significado.lower()]
    return problemas


def generar_significado_columnas():
    recursos = leer_json(RUTA_RECURSOS_BIGQUERY)
    perfil_por_recurso = leer_json(RUTA_PERFIL_COLUMNAS)
    significados = leer_json(RUTA_SIGNIFICADO_COLUMNAS) if os.path.exists(RUTA_SIGNIFICADO_COLUMNAS) else {}
    modelo = crear_modelo_potente().with_structured_output(SignificadoDeColumnas)

    for recurso in recursos:
        if recurso["id"] in significados:
            continue
        perfil = perfil_por_recurso[recurso["id"]]
        metadatos = {"tipo": recurso["tipo"], "nombre": recurso["nombre"], "columnas": perfil}
        if recurso["tipo"] == "vista":
            metadatos["sql"] = recurso["sql"]
        mensajes = [
            ("system", INSTRUCCIONES + "\nContexto:\n" + CONTEXTO_DE_NEGOCIO),
            ("user", json.dumps(metadatos, ensure_ascii=False, indent=1)),
        ]
        resultado = modelo.invoke(mensajes)
        problemas = encontrar_problemas(perfil, resultado)
        # Un segundo intento si se salto columnas o puso ejemplos
        if problemas:
            mensajes.append(("user", "Corrige y devuelve todo de nuevo: " + "; ".join(problemas)))
            resultado = modelo.invoke(mensajes)
            problemas = encontrar_problemas(perfil, resultado)
        if problemas:
            print("Aviso en", recurso["id"], problemas, "se borran los ejemplos")
        significados[recurso["id"]] = {
            columna.columna: quitar_ejemplos(columna.significado) for columna in resultado.columnas_explicadas}
        guardar_json(RUTA_SIGNIFICADO_COLUMNAS, significados)
        print("Columnas explicadas:", recurso["id"])


if __name__ == "__main__":
    generar_significado_columnas()
