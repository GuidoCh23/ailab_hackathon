from langchain_groq import ChatGroq

from configuracion import GROQ_CLAVES, GROQ_MODELO_LIGERO, GROQ_MODELO_POTENTE

# Pocos reintentos por clave: si una se quedo sin cuota del dia conviene pasar rapido a la siguiente
CANTIDAD_DE_REINTENTOS = 2
# Groq reserva el maximo de salida contra el limite por minuto, sin tope una sola llamada lo supera
MAXIMO_TOKENS_LIGERO = 2500
MAXIMO_TOKENS_POTENTE = 4000


def crear_modelos(nombre_modelo, maximo_tokens):
    # Un modelo por cada api key de Groq, cada clave tiene su propia cuota
    return [ChatGroq(model=nombre_modelo, api_key=clave, temperature=0, max_retries=CANTIDAD_DE_REINTENTOS,
                     max_tokens=maximo_tokens)
            for clave in GROQ_CLAVES]


def crear_modelos_ligeros():
    # Para tareas simples: elegir una herramienta, resumir resultados
    return crear_modelos(GROQ_MODELO_LIGERO, MAXIMO_TOKENS_LIGERO)


def crear_modelos_potentes():
    # Para tareas pesadas: decidir el flujo, escribir SQL, redactar la respuesta
    return crear_modelos(GROQ_MODELO_POTENTE, MAXIMO_TOKENS_POTENTE)


def crear_modelo_ligero():
    return crear_modelos_ligeros()[0]


def crear_modelo_potente():
    return crear_modelos_potentes()[0]


def unir_con_respaldo(modelos):
    # Usa el primero y, si falla por cuota u otro error, sigue con los demas en orden
    if len(modelos) == 1:
        return modelos[0]
    return modelos[0].with_fallbacks(modelos[1:])
