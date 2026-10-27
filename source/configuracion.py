import os

from dotenv import load_dotenv

CARPETA_PROYECTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(CARPETA_PROYECTO, ".env"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_KEY_2 = os.getenv("GROQ_API_KEY_2")
GROQ_API_KEY_3 = os.getenv("GROQ_API_KEY_3")
# Las api keys se usan en orden: si una se queda sin cuota sigue la siguiente
GROQ_CLAVES = [clave.strip() for clave in [GROQ_API_KEY, GROQ_API_KEY_2, GROQ_API_KEY_3] if clave and clave.strip()]
GROQ_MODELO_LIGERO = os.getenv("GROQ_MODEL_LIGERO", "qwen/qwen3.8-27b")
GROQ_MODELO_POTENTE = os.getenv("GROQ_MODEL_POTENTE", "openai/gpt-oss-120b")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_API_KEY_2 = os.getenv("GOOGLE_API_KEY_2")
# Igual que en Groq, la segunda api key de Gemini se usa si la primera falla
GOOGLE_CLAVES = [clave.strip() for clave in [GOOGLE_API_KEY, GOOGLE_API_KEY_2] if clave and clave.strip()]
GEMINI_MODELO_EMBEDDING = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")

GCP_PROYECTO = os.getenv("GCP_PROJECT_ID")
BIGQUERY_UBICACION = os.getenv("BQ_LOCATION", "US")
BIGQUERY_LIMITE_BYTES = int(os.getenv("BQ_MAX_BYTES_BILLED", "1000000000"))

# La ruta del .env es relativa a la carpeta del proyecto
ruta_credencial = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
if ruta_credencial and not os.path.isabs(ruta_credencial):
    ruta_credencial = os.path.join(CARPETA_PROYECTO, ruta_credencial)
RUTA_CREDENCIAL_BIGQUERY = ruta_credencial

# Archivos del catalogo
CARPETA_DATOS_CATALOGO = os.path.join(CARPETA_PROYECTO, "source", "catalogo", "datos")
RUTA_RECURSOS_BIGQUERY = os.path.join(CARPETA_DATOS_CATALOGO, "recursos_bigquery.json")
CARPETA_CHROMA = os.path.join(CARPETA_DATOS_CATALOGO, "chroma")

# Detalle de columnas, no va al embedding, lo usa el agente de detalle
CARPETA_EXTRAS = os.path.join(CARPETA_DATOS_CATALOGO, "extras")
RUTA_PERFIL_COLUMNAS = os.path.join(CARPETA_EXTRAS, "perfil_columnas.json")
RUTA_SIGNIFICADO_COLUMNAS = os.path.join(CARPETA_EXTRAS, "significado_columnas.json")
RUTA_MEDIDAS_DASHBOARDS = os.path.join(CARPETA_EXTRAS, "medidas_dashboards.json")

# Dashboards de Power BI en archivos pbix, con sus links publicados en links.json
CARPETA_DASHBOARDS = os.path.join(CARPETA_PROYECTO, "dashboards")
RUTA_LINKS_DASHBOARDS = os.path.join(CARPETA_DASHBOARDS, "links.json")

# Descripciones escritas a mano por las personas, un archivo por tipo de recurso
CARPETA_DESCRIPCIONES = os.path.join(CARPETA_PROYECTO, "descripciones")
RUTA_RECURSOS_DASHBOARDS = os.path.join(CARPETA_DATOS_CATALOGO, "recursos_dashboards.json")
