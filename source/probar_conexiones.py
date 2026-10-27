from conexiones.cliente_bigquery import ejecutar_consulta
from conexiones.modelo_groq import crear_modelo_ligero, crear_modelo_potente
from configuracion import GCP_PROYECTO

print("Probando Groq...")
for nombre_modelo, modelo in [("ligero", crear_modelo_ligero()), ("potente", crear_modelo_potente())]:
    respuesta = modelo.invoke("Responde solo con la palabra: listo")
    print(f"Groq {nombre_modelo} respondio:", respuesta.content)

print("\nProbando BigQuery...")
consulta_sql = f"""
SELECT ROUND(SUM(snapshot.amount_rc)) AS net_revenue_usd
FROM `{GCP_PROYECTO}.prod.v_revenue_snapshot` AS snapshot
JOIN `{GCP_PROYECTO}.raw.dim_account` AS cuenta ON cuenta.dimid_account = snapshot.dimid_account_code
JOIN `{GCP_PROYECTO}.raw.dim_channel` AS canal ON canal.dimid_channel_code = snapshot.dimid_channel_id
WHERE cuenta.level_02 = 'NR' AND snapshot.scenario_id = 'AC' AND snapshot.year = '2025' AND canal.level_03 <> 'ICO'
"""
tabla_resultado = ejecutar_consulta(consulta_sql)
print("Net Revenue AC 2025:", tabla_resultado["net_revenue_usd"][0], "(esperado 562394090)")
