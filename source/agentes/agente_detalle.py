from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware

from conexiones.modelo_groq import crear_modelos_ligeros
from herramientas.herramientas_detalle import buscar_valor, obtener_columnas

INSTRUCCIONES = """
Eres el agente Detalle de un catalogo de datos. Respondes preguntas sobre una columna, un atributo o un
valor especifico, por ejemplo donde esta el canal tradicional o que significa una columna.
- buscar_valor para encontrar en que tablas y vistas aparece un valor o una columna. Prueba tambien
  sinonimos, en espanol e ingles, y en singular, si la primera busqueda no encuentra nada.
- obtener_columnas para ver el significado de las columnas de un recurso y los valores reales de sus categorias.
  Pasale siempre un filtro con la palabra clave (pais, canal, escenario) para traer solo lo necesario.
Responde en espanol: recurso, columna y valor exacto con el que se filtra. Prefiere la capa prod.
Las columnas unicas o con datos personales no tienen valores listados: no los inventes.
Solo usa lo que devuelven las herramientas.
"""


def crear_agente_detalle():
    modelos = crear_modelos_ligeros()
    # Si la primera api key se queda sin cuota, el agente sigue con las demas
    respaldo = [ModelFallbackMiddleware(*modelos[1:])] if len(modelos) > 1 else []
    return create_agent(modelos[0], [buscar_valor, obtener_columnas], system_prompt=INSTRUCCIONES, middleware=respaldo)
