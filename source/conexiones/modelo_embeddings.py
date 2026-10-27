from langchain_google_genai import GoogleGenerativeAIEmbeddings

from configuracion import GEMINI_MODELO_EMBEDDING, GOOGLE_API_KEY, GOOGLE_CLAVES


def crear_modelo_embeddings():
    # Usa RETRIEVAL_DOCUMENT al indexar y RETRIEVAL_QUERY al buscar
    return GoogleGenerativeAIEmbeddings(model=GEMINI_MODELO_EMBEDDING, google_api_key=GOOGLE_API_KEY)


def crear_modelos_embeddings():
    # Un modelo por api key, en orden, el mismo modelo da los mismos vectores con cualquier key
    return [GoogleGenerativeAIEmbeddings(model=GEMINI_MODELO_EMBEDDING, google_api_key=clave)
            for clave in GOOGLE_CLAVES]
