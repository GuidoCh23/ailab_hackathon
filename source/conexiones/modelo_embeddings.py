from langchain_google_genai import GoogleGenerativeAIEmbeddings

from configuracion import GEMINI_MODELO_EMBEDDING, GOOGLE_API_KEY


def crear_modelo_embeddings():
    # Usa RETRIEVAL_DOCUMENT al indexar y RETRIEVAL_QUERY al buscar
    return GoogleGenerativeAIEmbeddings(model=GEMINI_MODELO_EMBEDDING, google_api_key=GOOGLE_API_KEY)
