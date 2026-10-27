import operator
from typing import Annotated, TypedDict


class EstadoDelChat(TypedDict):
    # Historial de la conversacion como pares (rol, texto)
    mensajes: list
    # Cada agente agrega su resultado al final de la lista
    resultados_de_agentes: Annotated[list, operator.add]
    siguiente_agente: str
    instruccion: str
    cantidad_de_pasos: int
    respuesta_final: str
