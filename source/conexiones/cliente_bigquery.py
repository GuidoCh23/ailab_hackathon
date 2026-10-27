from google.cloud import bigquery
from google.oauth2 import service_account

from configuracion import BIGQUERY_LIMITE_BYTES, BIGQUERY_UBICACION, GCP_PROYECTO, RUTA_CREDENCIAL_BIGQUERY


def crear_cliente_bigquery():
    credenciales = service_account.Credentials.from_service_account_file(RUTA_CREDENCIAL_BIGQUERY)
    return bigquery.Client(project=GCP_PROYECTO, credentials=credenciales, location=BIGQUERY_UBICACION)


def ejecutar_consulta(consulta_sql):
    cliente = crear_cliente_bigquery()
    # Limite de bytes para que ninguna consulta gaste la cuota
    configuracion_consulta = bigquery.QueryJobConfig(maximum_bytes_billed=BIGQUERY_LIMITE_BYTES)
    resultado = cliente.query(consulta_sql, job_config=configuracion_consulta).result()
    return resultado.to_dataframe(create_bqstorage_client=False)
