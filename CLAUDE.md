# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Workspace for an internal AI hackathon project (AI//LAB, Media Lab). The goal, per `CONVERSACION.md`: a chatbot that answers questions about **data lineage and business logic** of the BI landscape (sources: SAP, GCP/BigQuery, manual files, Nielsen; possibly SAC Actuals & EVAs), and tells the user whether a solution for their need already exists. Later versions: data-architecture and dashboard-design recommendations. Emphasis is on business logic, not just table structure.

Core use case (confirmed by the user): "I want to build a dashboard for X" → the chatbot answers **which existing dashboard to base it on, which data it uses (tables/views/measures), and where both are located**. Lineage and business logic serve that answer.

Target platform is **GCP**: data, metadata/catalog and the chatbot are meant to live there. `Datos_dummy/` was delivered by the data analysts as the input for building this (treat it as their deliverable; `CONTENIDO_DATA.md` is their cover message). It is a fictional replica of a LATAM Revenue BI model (fictional company *Sabora*) that the catalog/chatbot will be built and tested against. Docs and comments are in Spanish, so keep new docs/comments/identifiers in Spanish to match. Not a git repo.

Key docs:
- `Datos_dummy/LEEME.md` — model, amount semantics, the 14 seeded traps.
- `Datos_dummy/GUIA_CARGA_BIGQUERY.md` — load steps (personal-Gmail BigQuery sandbox via Colab/laptop/console, then Power BI saved as `.pbip`).
- `Datos_dummy/reporte_validacion.md` — generated checks + chatbot test questions with expected answers (use these to evaluate the chatbot).
- `CONTENIDO_DATA.md` — summary of what was delivered and the design decisions still awaiting user confirmation.
- `documentos/AI_LAB_2026 - 01 OCT.pdf` — hackathon deck (image-only; text transcription in `documentos/AI_LAB_2026 - 01 OCT.md`). Demo Day rubric: Impacto 30%, Innovación 20%, Uso de IA 20%, Viabilidad 20%, Demo 10%; its framework (Define → Context → Design → Build → Evaluate → Deploy → Observe → Improve, "start from the problem, not the technology") frames the deliverables.

## Commands

Chatbot app (root): the virtualenv lives **outside OneDrive** at `C:\Users\Guido\.venvs\ailab` (a `.venv` inside the OneDrive folder fails with file locks during sync). Secrets go in `.env` (template: `.env.example`, keep it without real values); the BigQuery read-only service account key is `credenciales/bigquery-lectura.json`. Both are gitignored.

```
C:\Users\Guido\.venvs\ailab\Scripts\python.exe -m pip install -r requirements.txt
C:\Users\Guido\.venvs\ailab\Scripts\python.exe scripts/probar_conexion.py   # expects NR AC 2025 = 562,394,090 and 17 views
```

Chatbot code lives in `source/` (LangGraph + LangChain, Groq via `langchain-groq` with two tiers: `crear_modelo_ligero()` = `qwen/qwen3.8-27b` for the agents (gpt-oss-20b garbled tool names and routed worse in tests; qwen also has its own daily quota), `crear_modelo_potente()` = `openai/gpt-oss-120b` for routing, SQL and descriptions; Gemini `gemini-embedding-001` embeddings + Chroma with one collection per resource type: dashboards, vistas, tablas; Streamlit UI). Modules import each other as top-level (`from configuracion import ...`), so run scripts as `python source/<script>.py` from the root; `source/probar_conexiones.py` checks Groq + BigQuery. Style rules for `source/` (user requirement): very simple code, full descriptive Spanish names (no abbreviations), only short inline comments, no header comments, no accents and no "/" or "//" in comments or text (use `os.path.join`, not pathlib's `/`).

Catalog pipeline, run from `source/` as modules (`python -m catalogo.<name>`), in order:
1. `extractor_bigquery` → `catalogo/datos/recursos_bigquery.json` (tables + views from INFORMATION_SCHEMA; each view has `lee_de` parsed from its SQL, which is the lineage; tables get row count, last load, `sistemas_origen`) and `catalogo/datos/extras/perfil_columnas.json` (per column of every table and view: `tipo_de_contenido` categoria/unico/medida/fecha, distinct count, and the real values only for categorias with ≤30 values; unique/personal columns never store values). No sample rows are kept: they made the LLM invent categories.
2. Descriptions are **written by hand, not by an LLM** (user decision 2026-10-26): `descripciones/dashboards.json`, `descripciones/vistas.json`, `descripciones/tablas.json` at the project root, each mapping a resource id to `descripcion`, `preguntas_que_responde`, `terminos_de_negocio`. People maintain them; Claude wrote the first version from the metadata, the view SQL and (for dashboards) the published reports. Keep them general (what the resource shows, what it is for, risks), never per-column detail. Never mention the intercompany exclusion rule (kept for the "Corregir" demo). `leer_descripciones()` in `catalogo/archivos_catalogo.py` merges the folder. There is no Groq description generator anymore.
3. `generador_significado_columnas` → `catalogo/datos/extras/significado_columnas.json` (still Groq, holds `CONTEXTO_DE_NEGOCIO`; one sentence per column, every column checked, one retry, any "por ejemplo" stripped by code). `extras/` never goes into the embedding: it is for a detail agent that answers questions about a specific column or value.
3b. `significado_de_vistas` → fills the views in `significado_columnas.json` by inheriting each column's meaning from its source table column, parsed from the view SQL (`alias.col AS name`, or `t.*` for the regional copies). No LLM. Column meanings of `manual_be_hq_latam`, `stock_os_si_so` and `stock_mv_si_so` were written by hand; the other 12 tables still come from the Groq generator.
4. `indexador_chroma` → `catalogo/datos/chroma/` (one collection per type, cosine, Gemini RETRIEVAL_DOCUMENT with title; embedding text is tipo, nombre, capa, descripcion, preguntas, terminos; md5 `huella` skips unchanged texts). Search helper: `catalogo.base_vectorial.buscar_en_coleccion`.
Dashboards (Power BI): the `.pbix` files live in `dashboards/` (made in Power BI web, published in the user's work-account "My workspace", visible only inside that organization; the account is on a Power BI trial that ends around 2026-12-24). `dashboards/links.json` maps each file name to its report link. `python -m catalogo.extractor_dashboards` (needs `pip install -r requirements_catalogo.txt`, which adds `pbixray`; kept out of `requirements.txt` so the cloud app does not need it) → `catalogo/datos/recursos_dashboards.json`: pages, on-screen texts, slicers, visuals with their fields, measures used, and `lee_de` = the BigQuery objects the dashboard really uses (columns in its visuals plus tables referenced by the DAX of its measures, followed recursively; the Power Query of each model table gives its dataset and object). Measure formulas go to `extras/medidas_dashboards.json` only; they contain the intercompany rule, so keep them out of descriptions until the user decides. `leer_todos_los_recursos()` returns dashboards plus BigQuery resources, and the tools find a dashboard by its title too.

Generators only fill missing ids, so delete an entry to regenerate it. Groq free tier limits `openai/gpt-oss-120b` to 8k tokens per minute and 200k tokens per day; the models retry on 429, but a full regeneration of the catalog can use most of a day's quota. A single request over 8k tokens fails outright (413), so keep agent inputs and tool outputs small.

Chatbot, run from `source/`: `streamlit run app.py` (UI), or `python -m grafo.grafo_principal` for one test question in the terminal. To test without spending the 120b quota, set `GROQ_MODEL_POTENTE=openai/gpt-oss-20b` in the shell (shell env wins over `.env`).
- `grafo/grafo_principal.py`: LangGraph loop. `orquestador` (powerful model, `json_schema` structured output) picks buscador, linaje, detalle or responder, up to 8 steps; `redactor` (powerful model) writes the answer. Code, not the LLM, adds the links: `agregar_links` appends the exact link of every catalog resource named in the answer (the LLM corrupted copied links). Before each decision `detectar_valores_mencionados` tells the orchestrator which real category values the question mentions, so it routes to detalle. Agents receive only the task and the user question, not earlier results, to stay under the token limit.
- `agentes/`: one `create_agent` (LangChain 1.x) per agent, light model. `herramientas/`: their tools. `catalogo_cargado.py` merges `recursos_bigquery.json`, descriptions and `extras/` in memory; Buscador ranks with similarity plus a small layer adjustment (prod +0.03, adhoc -0.02) and a 0.6 threshold; Detalle reads only `extras/`.
- Chroma: one cached `PersistentClient` behind a lock, with retries (`catalogo/base_vectorial.py`): the agents run tool calls in parallel and the chroma folder sits in OneDrive, both caused "Could not connect to tenant default_tenant". `obtener_columnas` takes a `filtro` so the Detalle agent does not exceed the per-minute input limit of the light model.
- Orchestrator uses `json_schema` with `strict=True` (gpt-oss-120b echoed the schema without it) and falls back to responder after 3 failed attempts.
- Groq keys: `GROQ_API_KEY`, `GROQ_API_KEY_2`, `GROQ_API_KEY_3` (the last two optional) are tried in order; `unir_con_respaldo` (with_fallbacks) for orchestrator and redactor, `ModelFallbackMiddleware` for the agents.
- Groq free tier: every model (gpt-oss-120b, qwen) has 200k tokens per day, and one full question uses roughly 10k to 40k. Testing the agent end to end exhausts both in a few hours; for the demo either save the quota or move to Groq's paid Dev tier.
- Still to build: Reglas, Datos and Corrector agents.
On Windows set `PYTHONIOENCODING=utf-8` when printing descriptions (they contain characters cp1252 can't encode).

Dummy data, run from `Datos_dummy/`:

```
python generar_datos_dummy.py              # regenerates raw/*.csv, esquemas/*.json, reporte_validacion.md (seed 20261013)
python generar_datos_dummy.py --semilla 7  # different variant
python generar_datos_dummy.py --salida DIR # write elsewhere (useful to test without overwriting)

pip install google-cloud-bigquery          # only needed for the loader
python cargar_a_bigquery.py --proyecto PROJECT_ID [--solo-vistas] [--ubicacion US]
```

There is no test suite: the generator's `validar()` runs the ~28 checks (unique keys, FK integrity, amount-column rules, sign conventions, PY 2026 = AC 2025, LF = AC on closed months), writes them to `reporte_validacion.md`, and exits 1 if any fail. Rerun the generator after any change to it.

## Architecture

- **`generar_datos_dummy.py`** (stdlib only, Python 3.8+ — do not add dependencies; it must run unmodified in Colab). Sections:
  1. `ESQUEMAS` — single source of truth for every table's columns/types; both the CSVs and the BigQuery JSON schemas are derived from it. Change columns here, never in `raw/` or `esquemas/` by hand.
  2. Fictional master data (`ENTIDADES`, `FX_BASE`, `ESCENARIOS`, `CUENTAS`, `CANALES`, …) and the `Generador` class, which fills `self.tablas` (name → list of dicts) table by table from a single seeded `random.Random`. Changing generation order or RNG calls changes all downstream data and the expected answers in the report.
  3. `escribir()` — CSV + JSON output.
  4. `validar()` — checks and chatbot test questions/expected answers.
- **`cargar_a_bigquery.py`** — creates datasets `raw`, `staging`, `prod`, `adhoc`; loads each `esquemas/*.json` + matching `raw/*.csv` into `raw` (WRITE_TRUNCATE); runs `sql/*.sql` in filename order after replacing `{PROYECTO}`. Statements are split naively on `;`, so never put a `;` inside SQL comments or string literals. Must stay within BigQuery sandbox limits: load jobs and DDL only, no INSERT/UPDATE/DELETE.
- **`sql/`** — view layers forming the lineage the catalog extractor reads from `INFORMATION_SCHEMA.VIEWS`: `01_staging.sql` (`v_revenue_model` + 12 regional views filtering by `dim_entity.region`), `02_prod.sql` (`v_revenue_snapshot`, the official Power BI view, intentionally unfiltered across scenarios/currencies), `03_adhoc.sql` (analyst duplicates with deliberately different logic).
- **`paquete_colab.zip`** — a copy of the two scripts + `sql/` for Colab upload. It is not rebuilt automatically: after editing any script or SQL file, rebuild it with the same layout (`generar_datos_dummy.py`, `cargar_a_bigquery.py`, `sql/*.sql`).

## Domain rules to respect

- The 14 traps in `LEEME.md` (mixed scenarios/currencies, pre-negative discounts, volume rows in the fact, intercompany CH10 included, manual files in thousands of USD, inconsistent month formats and key names, stale `dim_customer`, adhoc duplicates, etc.) are **intentional** demo material. Do not "fix" them. Notably, the intercompany exclusion rule (`dim_channel.level_03 = 'ICO'`) is deliberately left undocumented.
- Amount invariants enforced by validation: in AC `amount_rc = amount_ac`; in PY `amount_rc = amount_py`; for USD entities and volume rows all 8 amounts are equal.
- Official Net Revenue = sum of accounts with `dim_account.level_02 = 'NR'`, in `amount_rc`, one scenario at a time, excluding channel ICO.
- Fact join keys differ by name from dimension keys (e.g. `fct_revenue.dimid_account_code` → `dim_account.dimid_account`); check `sql/02_prod.sql` for the canonical joins.
- Tables are loaded without descriptions on purpose — filling them is the catalog's job.
