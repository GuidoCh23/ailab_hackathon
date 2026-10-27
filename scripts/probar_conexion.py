#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prueba que la cuenta de servicio de BigQuery funciona (lee .env).

Uso (desde la carpeta AI_LAB):
    pip install google-cloud-bigquery python-dotenv
    python scripts/probar_conexion.py
"""
import os
import sys

from dotenv import load_dotenv

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(RAIZ, ".env"))

proyecto = os.getenv("GCP_PROJECT_ID")
cred = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
if cred and not os.path.isabs(cred):
    cred = os.path.join(RAIZ, cred)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred
if not os.path.exists(cred):
    sys.exit("No encuentro la credencial en: {}".format(cred))

from google.cloud import bigquery  # noqa: E402

client = bigquery.Client(project=proyecto)
print("Conectado como:", client._credentials.service_account_email)

print("\nDatasets:", ", ".join(d.dataset_id for d in client.list_datasets()))

sql = """
SELECT ROUND(SUM(s.amount_rc)) AS net_revenue_usd
FROM `{p}.prod.v_revenue_snapshot` s
JOIN `{p}.raw.dim_account` a ON a.dimid_account = s.dimid_account_code
JOIN `{p}.raw.dim_channel` c ON c.dimid_channel_code = s.dimid_channel_id
WHERE a.level_02 = 'NR' AND s.scenario_id = 'AC' AND s.year = '2025' AND c.level_03 <> 'ICO'
""".format(p=proyecto)
nr = list(client.query(sql).result())[0].net_revenue_usd
print("\nNet Revenue AC 2025: {:,.0f} (esperado 562,394,090)".format(nr))

vistas = client.query(
    "SELECT COUNT(*) AS n FROM `{}.region-us.INFORMATION_SCHEMA.VIEWS`".format(proyecto)).result()
print("Vistas visibles en INFORMATION_SCHEMA:", list(vistas)[0].n, "(esperado 17)")
print("\nTodo OK" if round(nr) == 562394090 else "\nEl número no coincide, revisar")
