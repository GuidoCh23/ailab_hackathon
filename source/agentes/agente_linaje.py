from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware

from conexiones.modelo_groq import crear_modelos_ligeros
from herramientas.herramientas_linaje import obtener_dependientes, obtener_ficha, obtener_origenes, obtener_sql_de_vista

INSTRUCCIONES = """
Eres el agente Linaje de un catalogo de datos. Explicas de donde salen los datos de un recurso, quien lo usa
y como esta construido.
- obtener_ficha para la descripcion, ubicacion, columnas, ultima carga y sistemas de origen.
- obtener_origenes para saber de que vistas y tablas sale, hasta el origen.
- obtener_dependientes para saber que vistas o dashboards lo usan.
- obtener_sql_de_vista cuando hay que explicar filtros, uniones o calculos de una vista.
Distingue la relacion directa de la indirecta, tal como la marcan las herramientas.
Responde en espanol, ordenado y breve, con los nombres completos de los recursos. Solo usa lo que devuelven las herramientas.
"""


def crear_agente_linaje():
    herramientas = [obtener_ficha, obtener_origenes, obtener_dependientes, obtener_sql_de_vista]
    modelos = crear_modelos_ligeros()
    # Si la primera api key se queda sin cuota, el agente sigue con las demas
    respaldo = [ModelFallbackMiddleware(*modelos[1:])] if len(modelos) > 1 else []
    return create_agent(modelos[0], herramientas, system_prompt=INSTRUCCIONES, middleware=respaldo)
