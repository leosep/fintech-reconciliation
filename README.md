# Fintech Reconciliation Automation Platform

Plataforma simple de **conciliación automática de pagos**: compara transacciones
de un sistema interno contra las reportadas por un banco/procesador de pagos,
detecta diferencias y genera un reporte Excel.

> Para una guía paso a paso pensada para cualquier persona (no solo developers),
> ve el archivo **`MANUAL_DE_USO.md`**.

## Stack

- Python 3.11+
- FastAPI + Uvicorn (API REST)
- Pandas (lectura de CSV/Excel)
- SQLAlchemy + SQLite (base de datos, sin instalación aparte)
- OpenPyXL (reportes Excel)
- Pytest (tests)

## Estructura

```
fintech-reconciliation/
├── app/
│   ├── main.py                  # API FastAPI (endpoints)
│   ├── database.py               # Conexión SQLite + SQLAlchemy
│   ├── models.py                 # Tablas (transactions, bank_transactions,
│   │                              #   reconciliation_results, reconciliation_runs, audit_log)
│   ├── schemas.py                 # Esquemas Pydantic de entrada/salida
│   └── services/
│       ├── normalization.py       # Normaliza IDs, montos y fechas
│       ├── ingestion.py           # Lee e importa CSV/Excel
│       ├── reconciliation.py      # Motor de conciliación + registro de corridas
│       ├── report.py              # Genera el reporte Excel
│       └── audit.py               # Bitácora de auditoría
├── automation/
│   ├── n8n_workflow_example.json  # Workflow de n8n listo para importar
│   └── INTEGRACION_AUTOMATIZACION.md  # Guía Make / n8n / Power Automate
├── jobs/
│   └── run_reconciliation.py     # Script de demo por línea de comandos (todo en uno)
├── data/
│   ├── input/                     # Archivos de ejemplo (interno + banco)
│   └── output/                    # Aquí se guardan los reportes Excel generados
├── tests/                          # Tests unitarios e integración (pytest)
├── requirements.txt
├── MANUAL_DE_USO.md               # Manual paso a paso
└── README.md
```

## Instalación rápida

```bash
python -m venv venv
source venv/bin/activate      # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Opción 1: probar todo con un solo comando (sin API)

```bash
python jobs/run_reconciliation.py
```

Esto importa los archivos de ejemplo en `data/input/`, corre la conciliación
y deja un Excel en `data/output/`.

## Opción 2: usar la API

```bash
uvicorn app.main:app --reload
```

Luego abre `http://127.0.0.1:8000/docs` para ver y probar todos los endpoints
desde el navegador (Swagger UI).

### Endpoints principales

| Método | Ruta                              | Descripción                                   |
|--------|-----------------------------------|------------------------------------------------|
| POST   | `/api/import/internal`            | Sube un CSV/Excel de transacciones internas    |
| POST   | `/api/import/bank`                | Sube un CSV/Excel de transacciones del banco   |
| GET    | `/api/transactions`               | Lista transacciones internas                   |
| GET    | `/api/transactions/bank`          | Lista transacciones del banco                  |
| POST   | `/api/reconciliation/run`         | Ejecuta el motor de conciliación                |
| GET    | `/api/reconciliation/results`     | Lista todos los resultados                     |
| GET    | `/api/reconciliation/exceptions`  | Lista solo lo que NO fue un MATCH               |
| GET    | `/api/reconciliation/runs`        | Historial de corridas (auditoría)               |
| GET    | `/api/reports/excel`              | Genera y descarga el reporte Excel              |
| GET    | `/api/reports/excel/{file_name}`  | Descarga un reporte ya generado por su nombre   |
| GET    | `/api/audit/log`                  | Bitácora completa de todas las acciones         |
| POST   | `/api/automation/run-pipeline`    | **Endpoint "todo en uno" para Make/n8n/Power Automate**: importa ambos archivos, concilia y genera el reporte en una sola llamada |

### Automatización con Make / n8n / Power Automate

El endpoint `POST /api/automation/run-pipeline` está diseñado específicamente
para ser llamado desde un nodo/módulo HTTP de estas herramientas: recibe los
dos archivos (`internal_file`, `bank_file`), hace todo el proceso (importar +
conciliar + reportar) y devuelve un JSON con el resumen y la URL de descarga
del Excel. Cada llamada queda registrada con el parámetro `triggered_by`
(`n8n`, `make`, `power_automate`, etc.) tanto en `reconciliation_runs` como
en `audit_log`.

Ver la guía completa, con un workflow de n8n listo para importar, en:
**`automation/INTEGRACION_AUTOMATIZACION.md`**

## Formato esperado de los archivos CSV/Excel

Columnas obligatorias (los nombres pueden estar en español o inglés,
mayúsculas o minúsculas):

| Concepto      | Nombres aceptados                     |
|---------------|-----------------------------------------|
| Referencia    | `transaction_id`, `referencia`, `reference`, `bank_reference`, `id` |
| Monto         | `amount`, `monto`, `importe`            |
| Fecha         | `date`, `fecha`, `transaction_date`     |
| Cliente (opc.)| `customer`, `cliente`                    |
| Moneda (opc.) | `currency`, `moneda`                     |

## Estados de conciliación

- `MATCH`: misma referencia, mismo monto en ambas fuentes.
- `AMOUNT_DIFFERENCE`: misma referencia, monto distinto.
- `MISSING_IN_BANK`: existe en el sistema interno pero no llegó al banco.
- `MISSING_INTERNAL`: el banco reporta algo que no existe internamente.
- `DUPLICATE`: la misma referencia aparece más de una vez en una fuente.

## Correr los tests

```bash
pytest -v
```

## Notas de diseño

- Se usa **SQLite** para que el proyecto funcione sin instalar nada más. El
  código usa SQLAlchemy, así que migrar a PostgreSQL o SQL Server solo
  requiere cambiar la variable de entorno `DATABASE_URL`.
- La normalización de referencias (`TX-001` → `TX001`) y de montos
  (`RD$ 1,500.00` → `1500.00`) vive en `app/services/normalization.py` y está
  cubierta por tests unitarios.
- El motor de conciliación (`app/services/reconciliation.py`) es la pieza
  central: agrupa por referencia normalizada, detecta duplicados y clasifica
  cada transacción.
- Cada corrida de conciliación (manual, por API, por CLI, o disparada desde
  Make/n8n/Power Automate) queda registrada en la tabla `reconciliation_runs`
  y en `audit_log`, para poder responder "¿qué pasó con las transacciones de
  ayer, y qué la disparó?".
- El endpoint `/api/automation/run-pipeline` está pensado como el punto de
  entrada único para herramientas de automatización low-code: una sola
  llamada HTTP hace todo el proceso (importar, conciliar, reportar).
