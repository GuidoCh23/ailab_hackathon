import json
import re
from typing import Literal

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from agentes.agente_buscador import crear_agente_buscador
from agentes.agente_detalle import crear_agente_detalle
from agentes.agente_linaje import crear_agente_linaje
from conexiones.modelo_groq import crear_modelos_potentes, unir_con_respaldo
from grafo.estado import EstadoDelChat
from herramientas.catalogo_cargado import cargar_catalogo
from herramientas.herramientas_detalle import detectar_valores_mencionados, normalizar

MAXIMO_DE_PASOS = 8
CANTIDAD_DE_MENSAJES_DE_HISTORIAL = 6
MAXIMO_VECES_POR_AGENTE = 2
# Palabras que indican una pregunta de origen o de impacto de los datos
PALABRAS_DE_LINAJE = ["usan", "usa ", "utiliza", "afecta", "depende", "de donde sale", "origen", "alimenta",
                      "linaje", "si cambio", "si modifico", "consume"]

INSTRUCCIONES_ORQUESTADOR = """
Eres el orquestador de un chatbot que ayuda a encontrar dashboards, vistas y tablas de datos de la empresa
Sabora, y a entender de donde salen sus datos. Decides que agente trabaja en cada paso.
Regla principal: si el usuario quiere hacer, buscar o basarse en un dashboard o reporte, el primer paso
es siempre buscador, aunque la pregunta mencione valores como presupuesto, un pais o un canal.
Lo mismo si pregunta donde estan los datos de un tema (best estimate, stock, ventas de un pais): eso es buscador.
- buscador: encuentra dashboards, vistas o tablas por tema o por nombre. Empieza por aqui cuando el usuario
  quiere hacer un dashboard o busca datos sobre algo y aun no se sabe que recurso es.
- linaje: da la ficha de un recurso, de que lee, quien lo usa y su SQL. Usalo para preguntas de impacto
  (si cambio o modifico algo, que se afecta, quien lo usa) y de origen (de donde salen los datos).
  Acepta el nombre del recurso aunque sea corto, como dim_entity o Gross to Net; si el usuario no da
  ningun nombre, primero usa buscador.
- detalle: cuando el usuario menciona una columna, un atributo o un valor especifico
  (un canal, un pais, una moneda, una cuenta, un cliente), pregunta con que valor filtrar
  o que significa una columna. Ejemplos: donde esta el canal tradicional, que valores tiene escenario.
- responder: solo cuando los resultados cubren todas las partes de la pregunta, o cuando es un saludo.
Si te indican valores de categorias mencionados en la pregunta y el usuario pregunta por ese valor o como filtrarlo,
busca algo especifico: usa detalle. Si solo los menciona como contexto, son una pista y nada mas.
Si la pregunta tiene varias partes, encarga cada parte al agente que corresponde antes de responder.
Da al agente una instruccion concreta, con los nombres exactos de recursos que ya se conocen.
Los agentes no hablan con el usuario: nunca les pidas que pregunten algo al usuario. Si falta el nombre de un
recurso, encarga al agente que lo busque. Solo si de verdad no se puede buscar, elige responder y que la respuesta lo pida.
Si un agente no encontro algo, prueba con otro agente antes de responder que no existe.
No repitas una tarea que un agente ya hizo.
"""

INSTRUCCIONES_REDACTOR = """
Eres el asistente de un catalogo de datos de la empresa Sabora. Responde en el idioma del usuario, claro y breve,
usando solo lo que encontraron los agentes. Reglas:
- Si quiere hacer un dashboard: di en que dashboard existente basarse, que muestra, que vistas y tablas usa
  y donde estan. Nombra los dashboards por su titulo, como Resumen Ejecutivo.
- Los dashboards de Power BI (capa powerbi) y las vistas de la capa prod son los oficiales. Recomiendalos primero.
  Las vistas staging son intermedias y las tablas raw son datos de origen: no las llames no oficiales.
  Solo la capa adhoc es no oficial: si mencionas uno de adhoc, avisalo. No listes recursos que no vienen al caso.
- Si desaconsejas un recurso, explica el motivo con lo que dice su descripcion (por ejemplo errores de calculo
  o datos desactualizados) y nombra la alternativa oficial si los agentes la encontraron.
- En linaje distingue lo que usa un recurso directamente de lo que usa a traves de otro recurso.
  Si preguntan que se afecta o quien usa algo, lista todos los recursos por nombre, tambien los no oficiales.
- Escribe las vistas y tablas con su capa, como prod.v_revenue_snapshot, y listalas siempre por nombre.
  Lo unico que no escribes son los links ni marcadores como [Enlace]: se agregan solos al final de la respuesta.
- Nombres de recursos, columnas, valores y filtros: escribelos exactamente como aparecen en los resultados.
  Nunca escribas un filtro con una columna o un valor que no aparezca literalmente en los resultados.
- Si una parte de la pregunta no fue investigada o no se encontro, dilo con honestidad en vez de suponer.
- Explica que significa una columna solo con el significado que trajo un agente. Si no lo trajo, dilo.
- No afirmes que un recurso usa o no usa a otro si ningun agente consulto su linaje con exito, y no hables de
  quien usa un recurso si no lo preguntaron. Que un agente no encuentre un nombre no significa que nadie lo use.
- Nunca digas que una tabla raw o una vista staging no es oficial: raw son datos de origen, staging son intermedias.
- Si es un saludo o preguntan que puedes hacer, explica en pocas lineas que ayudas a: encontrar en que dashboard
  basarse para un reporte nuevo y que datos usa, encontrar la vista o tabla correcta para un tema, ver de donde
  salen los datos y que se afecta si cambia algo, y saber que significa una columna o con que valor filtrar.
  Solo en ese caso termina con dos o tres preguntas de ejemplo que usen nombres reales, como Resumen Ejecutivo,
  prod.v_revenue_snapshot o raw.dim_entity. Nunca inventes nombres de recursos ni de columnas.
"""


class DecisionDelOrquestador(BaseModel):
    siguiente_agente: Literal["buscador", "linaje", "detalle", "responder"]
    instruccion: str = Field(description="tarea concreta para el agente, vacia si es responder")


def formatear_historial(mensajes):
    recientes = mensajes[-CANTIDAD_DE_MENSAJES_DE_HISTORIAL:]
    return "\n".join(f"{rol}: {texto}" for rol, texto in recientes)


def formatear_resultados(resultados_de_agentes):
    if not resultados_de_agentes:
        return "Todavia ningun agente trabajo."
    return "\n\n".join(
        f"Agente {resultado['agente']}, tarea: {resultado['instruccion']}\n{resultado['resultado']}"
        for resultado in resultados_de_agentes)


def armar_contexto(estado):
    return (f"Conversacion:\n{formatear_historial(estado['mensajes'])}\n\n"
            f"Resultados de los agentes:\n{formatear_resultados(estado['resultados_de_agentes'])}")


def ultima_pregunta(mensajes):
    return next((texto for rol, texto in reversed(mensajes) if rol == "usuario"), "")


def es_pregunta_de_linaje(pregunta):
    texto = normalizar(pregunta)
    return any(palabra in texto for palabra in PALABRAS_DE_LINAJE)


def armar_pistas(estado):
    pregunta = ultima_pregunta(estado["mensajes"])
    pistas = ""
    if es_pregunta_de_linaje(pregunta):
        pistas += ("\n\nEs una pregunta de linaje o impacto: usa linaje, que distingue el uso directo del uso "
                   "a traves de otros recursos. Si falta el nombre del recurso, que lo busque con el que dio el usuario.")
    valores_mencionados = detectar_valores_mencionados(pregunta)
    if valores_mencionados:
        pistas += "\n\nValores de categorias mencionados en la pregunta:\n" + "\n".join(valores_mencionados)
    return pistas


def crear_nodo_orquestador():
    # json_schema estricto obliga al modelo a devolver exactamente la decision
    modelo = unir_con_respaldo([
        modelo.with_structured_output(DecisionDelOrquestador, method="json_schema", strict=True)
        for modelo in crear_modelos_potentes()])

    def orquestar(estado):
        contexto = armar_contexto(estado) + armar_pistas(estado)
        # Si la decision no se puede leer se reintenta, y al final se responde con lo que ya hay
        decision = DecisionDelOrquestador(siguiente_agente="responder", instruccion="")
        for _ in range(3):
            try:
                decision = modelo.invoke([("system", INSTRUCCIONES_ORQUESTADOR), ("user", contexto)])
                break
            except Exception as error:
                print(f"Error en orquestador: {str(error)[:200]}")
        return {
            "siguiente_agente": decision.siguiente_agente,
            "instruccion": decision.instruccion,
            "cantidad_de_pasos": estado["cantidad_de_pasos"] + 1,
        }
    return orquestar


def crear_nodo_de_agente(nombre_agente, agente):
    def trabajar(estado):
        # Solo la tarea y la pregunta, para no pasar el limite de tokens por minuto de Groq
        entrada = f"Tarea: {estado['instruccion']}\nPregunta del usuario: {ultima_pregunta(estado['mensajes'])}"
        # A veces el modelo llama mal a una herramienta, se reintenta una vez
        texto_resultado = f"El agente {nombre_agente} no pudo completar la tarea por un error tecnico."
        for _ in range(2):
            try:
                respuesta = agente.invoke({"messages": [("user", entrada)]})
                texto_resultado = respuesta["messages"][-1].content
                break
            except Exception as error:
                print(f"Error en {nombre_agente}: {str(error)[:200]}")
        resultado = {"agente": nombre_agente, "instruccion": estado["instruccion"], "resultado": texto_resultado}
        return {"resultados_de_agentes": [resultado]}
    return trabajar


def esta_mencionado(recurso, respuesta):
    nombres = [recurso["nombre"]] + ([recurso["titulo"]] if recurso.get("titulo") else [])
    return any(re.search(rf"(?<![\w.]){re.escape(nombre)}(?!\w)", respuesta, re.IGNORECASE) for nombre in nombres)


def corregir_capas(respuesta):
    # Si el modelo escribe un objeto real con la capa equivocada, se pone su nombre completo correcto
    nombre_por_objeto = {}
    for recurso in cargar_catalogo().values():
        objeto = recurso["nombre"].split(".")[-1]
        nombre_por_objeto.setdefault(objeto, []).append(recurso["nombre"])

    def reemplazar(coincidencia):
        candidatos = nombre_por_objeto.get(coincidencia.group(2), [])
        if coincidencia.group(0) in candidatos or len(candidatos) != 1:
            return coincidencia.group(0)
        return candidatos[0]
    return re.sub(r"\b(raw|staging|prod|adhoc)\.(\w+)", reemplazar, respuesta)


def agregar_links(respuesta):
    # Los links los pone el codigo, copiados por el modelo se pueden romper
    respuesta = re.sub(r"\s*\[(enlace|link)[^\]]*\](\([^)]*\))?", "", respuesta, flags=re.IGNORECASE)
    mencionados = [recurso for recurso in cargar_catalogo().values() if esta_mencionado(recurso, respuesta)]
    if not mencionados:
        return respuesta
    lineas = []
    for recurso in mencionados:
        if recurso["tipo"] == "dashboard":
            lineas.append(f"- [{recurso['titulo']}]({recurso['link']}) (dashboard en Power BI)")
        else:
            lineas.append(f"- [{recurso['nombre']}]({recurso['link']}) ({recurso['tipo']} en BigQuery)")
    return respuesta + "\n\n**Donde encontrarlos:**\n" + "\n".join(lineas)


def crear_nodo_redactor():
    modelo = unir_con_respaldo(crear_modelos_potentes())

    def redactar(estado):
        respuesta = modelo.invoke([("system", INSTRUCCIONES_REDACTOR), ("user", armar_contexto(estado))])
        return {"respuesta_final": agregar_links(corregir_capas(respuesta.content))}
    return redactar


def elegir_siguiente_nodo(estado):
    # Corta el ciclo si el orquestador da demasiadas vueltas o insiste con el mismo agente
    veces_del_agente = sum(1 for resultado in estado["resultados_de_agentes"]
                           if resultado["agente"] == estado["siguiente_agente"])
    if (estado["siguiente_agente"] == "responder" or estado["cantidad_de_pasos"] >= MAXIMO_DE_PASOS
            or veces_del_agente >= MAXIMO_VECES_POR_AGENTE):
        return "redactor"
    return estado["siguiente_agente"]


def crear_grafo():
    grafo = StateGraph(EstadoDelChat)
    grafo.add_node("orquestador", crear_nodo_orquestador())
    grafo.add_node("buscador", crear_nodo_de_agente("buscador", crear_agente_buscador()))
    grafo.add_node("linaje", crear_nodo_de_agente("linaje", crear_agente_linaje()))
    grafo.add_node("detalle", crear_nodo_de_agente("detalle", crear_agente_detalle()))
    grafo.add_node("redactor", crear_nodo_redactor())

    grafo.add_edge(START, "orquestador")
    grafo.add_conditional_edges("orquestador", elegir_siguiente_nodo,
                                ["buscador", "linaje", "detalle", "redactor"])
    for nombre_agente in ["buscador", "linaje", "detalle"]:
        grafo.add_edge(nombre_agente, "orquestador")
    grafo.add_edge("redactor", END)
    return grafo.compile()


def crear_estado_inicial(mensajes):
    return {"mensajes": mensajes, "resultados_de_agentes": [], "siguiente_agente": "",
            "instruccion": "", "cantidad_de_pasos": 0, "respuesta_final": ""}


if __name__ == "__main__":
    grafo_del_chat = crear_grafo()
    pregunta = "quiero hacer un dashboard de venta neta por canal, en que me baso y que datos uso?"
    for actualizacion in grafo_del_chat.stream(crear_estado_inicial([("usuario", pregunta)]), stream_mode="updates"):
        for nombre_nodo, cambios in actualizacion.items():
            print(f"\n[{nombre_nodo}]", json.dumps(cambios, ensure_ascii=False)[:500])
