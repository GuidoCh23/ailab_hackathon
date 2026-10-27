from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware

from conexiones.modelo_groq import crear_modelos_ligeros
from herramientas.herramientas_buscador import (buscar_dashboards, buscar_por_nombre, buscar_por_sistema_de_origen,
                                                buscar_tablas, buscar_vistas)

INSTRUCCIONES = """
Eres el agente Buscador de un catalogo de datos. Tu trabajo es encontrar los dashboards, vistas o tablas
que mejor responden a la tarea.
- Elige la herramienta segun lo que se pide: dashboards para reportes, vistas para datos ya preparados,
  tablas para datos de origen. Si no esta claro, busca en mas de una.
- Si el usuario escribe un nombre concreto, usa buscar_por_nombre.
- Si pregunta que tablas vienen de un sistema (ERP, MDM, planning tool, un archivo), usa buscar_por_sistema_de_origen.
- Los dashboards de Power BI (capa powerbi) y las vistas de la capa prod son los oficiales. Las de staging
  son intermedias y las tablas raw son los datos de origen: ambas son validas. Solo adhoc es no oficial, avisalo.
  Nombra cada dashboard por su titulo y di que datos usa.
- No confies solo en la similitud: lee las descripciones y ordena los resultados por lo que de verdad
  responde la tarea.
Responde en espanol con la lista final: nombre completo, tipo, capa y en una oracion por que sirve.
Si la descripcion de un recurso advierte errores, riesgos, unidades especiales o datos desactualizados, copia esa
advertencia completa: el usuario la necesita.
Si nada sirve, dilo. No inventes recursos.
"""


def crear_agente_buscador():
    herramientas = [buscar_dashboards, buscar_vistas, buscar_tablas, buscar_por_nombre, buscar_por_sistema_de_origen]
    modelos = crear_modelos_ligeros()
    # Si la primera api key se queda sin cuota, el agente sigue con las demas
    respaldo = [ModelFallbackMiddleware(*modelos[1:])] if len(modelos) > 1 else []
    return create_agent(modelos[0], herramientas, system_prompt=INSTRUCCIONES, middleware=respaldo)
