# Manual de uso — Fintech Reconciliation Automation Platform

Este manual explica, paso a paso, cómo instalar y usar el proyecto **aunque
nunca lo hayas usado antes**.

---

## 1. ¿Qué hace este proyecto?

Recibe dos archivos (uno con las transacciones de "tu sistema" y otro con las
transacciones que reporta "el banco"), los compara automáticamente, y te dice
exactamente en qué coinciden y en qué no. Al final genera un Excel con el
resumen y el detalle de todo lo que necesita revisión manual.

---

## 2. Requisitos

- Tener **Python 3.11 o superior** instalado.
  - Para comprobarlo, abre una terminal (o "Símbolo del sistema" en Windows) y escribe:
    ```bash
    python --version
    ```
  - Si no lo tienes, descárgalo desde https://www.python.org/downloads/

No necesitas instalar ninguna base de datos aparte: el proyecto crea su
propio archivo de base de datos (`reconciliation.db`) automáticamente.

---

## 3. Instalación (solo se hace una vez)

1. Descomprime el archivo `.zip` en la carpeta donde quieras trabajar.
2. Abre una terminal dentro de la carpeta `fintech-reconciliation`.
3. Crea un entorno virtual (esto mantiene las librerías del proyecto separadas
   del resto de tu computadora):

   ```bash
   python -m venv venv
   ```

4. Actívalo:

   - **Windows**:
     ```bash
     venv\Scripts\activate
     ```
   - **Mac / Linux**:
     ```bash
     source venv/bin/activate
     ```

   Sabrás que funcionó porque verás `(venv)` al inicio de la línea de tu terminal.

5. Instala las dependencias:

   ```bash
   pip install -r requirements.txt
   ```

   Esto puede tardar 1-2 minutos la primera vez.

---

## 4. Forma más rápida de probarlo (recomendada para empezar)

El proyecto ya incluye dos archivos de ejemplo en `data/input/`:

- `internal_transactions.csv` (simula tu sistema interno)
- `bank_transactions.csv` (simula lo que reporta el banco)

Para correr todo el proceso de una sola vez, ejecuta:

```bash
python jobs/run_reconciliation.py
```

Vas a ver algo como esto en pantalla:

```
[1/4] Importando transacciones internas...
[2/4] Importando transacciones bancarias...
[3/4] Ejecutando motor de conciliación...
      MATCH:                3
      MISSING_IN_BANK:      1
      MISSING_INTERNAL:     1
      AMOUNT_DIFFERENCE:    1
      DUPLICATE:            1
[4/4] Generando reporte Excel...
      Reporte generado en: .../data/output/reconciliation_2026-08-25_....xlsx
```

Abre ese archivo Excel: tendrá una hoja **Summary** (totales) y una hoja
**Exceptions** (el detalle de todo lo que no fue un `MATCH` perfecto, con el
monto esperado, el monto real y la diferencia).

### ¿Quiero usar mis propios archivos?

```bash
python jobs/run_reconciliation.py --internal "ruta/a/mi_archivo_interno.csv" --bank "ruta/a/mi_archivo_banco.xlsx"
```

Acepta tanto `.csv` como `.xlsx`.

**Columnas que debe tener tu archivo** (no importa el orden, ni si usas
mayúsculas/minúsculas, ni si están en español o inglés):

| Dato necesario | Nombres de columna que reconoce                          |
|-----------------|-----------------------------------------------------------|
| Referencia      | `transaction_id`, `referencia`, `reference`, `bank_reference`, `id` |
| Monto           | `amount`, `monto`, `importe`                               |
| Fecha           | `date`, `fecha`, `transaction_date`                        |
| Cliente (opcional) | `customer`, `cliente`                                    |
| Moneda (opcional)  | `currency`, `moneda`                                     |

Si tu archivo no tiene alguna de las columnas obligatorias (referencia, monto,
fecha), el programa te lo dirá con un mensaje claro en pantalla.

---

## 5. Usarlo como API (para integrarlo con otros sistemas)

Si en vez de un script quieres una API web (por ejemplo, para que otra
aplicación suba archivos automáticamente), levanta el servidor:

```bash
uvicorn app.main:app --reload
```

Vas a ver un mensaje diciendo que el servidor corre en `http://127.0.0.1:8000`.

Abre en tu navegador:

```
http://127.0.0.1:8000/docs
```

Ahí verás una interfaz visual (Swagger) donde puedes:

1. **Subir tu archivo interno** → endpoint `POST /api/import/internal`
2. **Subir tu archivo del banco** → endpoint `POST /api/import/bank`
3. **Ejecutar la conciliación** → endpoint `POST /api/reconciliation/run`
4. **Ver los resultados** → endpoint `GET /api/reconciliation/results`
5. **Ver solo las excepciones** (lo que necesita revisión) → `GET /api/reconciliation/exceptions`
6. **Descargar el reporte Excel** → `GET /api/reports/excel`
7. **Ver el historial de corridas** → `GET /api/reconciliation/runs`
8. **Ver la bitácora de auditoría** → `GET /api/audit/log`
9. **Hacer todo de un solo golpe** (pensado para automatización) → `POST /api/automation/run-pipeline`

Para cada endpoint, haz clic en "Try it out", completa lo que pida (por
ejemplo, seleccionar un archivo) y luego "Execute". La respuesta aparece
debajo, y en el caso del reporte Excel, el navegador te lo descarga.

---

## 6. Entendiendo los resultados

| Estado               | Qué significa                                                        |
|----------------------|-----------------------------------------------------------------------|
| `MATCH`              | Todo bien: la transacción aparece en ambos lados con el mismo monto.  |
| `AMOUNT_DIFFERENCE`  | Aparece en ambos lados, pero el monto no coincide. Requiere revisión. |
| `MISSING_IN_BANK`    | Está en tu sistema pero el banco no la reporta. Puede ser un pago que no se procesó todavía, o un error. |
| `MISSING_INTERNAL`   | El banco reporta algo que tu sistema no tiene registrado. Revisar con cuidado (puede ser un cobro indebido o una transacción no registrada). |
| `DUPLICATE`          | La misma referencia aparece más de una vez en una de las dos fuentes. Revisar manualmente antes de conciliar. |

---

## 7. Automatizarlo con Make, n8n o Power Automate

Si quieres que este proceso corra solo todos los días (sin que nadie tenga
que entrar a subir archivos a mano), el proyecto incluye un endpoint pensado
exactamente para eso:

```
POST /api/automation/run-pipeline
```

En **una sola llamada**, este endpoint importa el archivo interno, importa
el archivo del banco, ejecuta la conciliación y genera el reporte Excel.
Devuelve un JSON con el resumen y la URL para descargar el Excel.

### ¿Cómo se conecta desde cada herramienta?

- **n8n**: en la carpeta `automation/` hay un archivo
  `n8n_workflow_example.json` que puedes importar directamente en n8n
  (menú "Import from File"). Ya trae armado el flujo: todos los días a las
  7:00 AM, lee los archivos, llama a este endpoint, y si hay excepciones
  envía un correo con el reporte adjunto.
- **Make**: arma un escenario con un módulo que lea el correo/carpeta donde
  llega el archivo del banco, y un módulo HTTP que haga un `POST` a
  `/api/automation/run-pipeline` enviando los dos archivos.
- **Power Automate**: usa un disparador de Outlook/SharePoint para detectar
  el archivo nuevo, y una acción HTTP que llame al mismo endpoint.

La guía detallada, con ejemplos de configuración para cada herramienta, está
en **`automation/INTEGRACION_AUTOMATIZACION.md`**.

### ¿Cómo sé qué disparó cada ejecución?

Cada vez que se corre la conciliación (a mano, desde la API, desde el script,
o desde Make/n8n/Power Automate) queda un registro. Puedes consultarlo en:

- `GET /api/reconciliation/runs` → historial de corridas con totales y quién
  las disparó.
- `GET /api/audit/log` → bitácora detallada de cada importación y ejecución.

Esto te permite responder en cualquier momento: **"¿qué pasó con las
transacciones de ayer, y qué proceso lo disparó?"**

---

## 8. Correr las pruebas automáticas (opcional, para desarrolladores)

Si quieres verificar que la lógica de normalización, conciliación y el
pipeline de automatización siguen funcionando correctamente después de algún
cambio:

```bash
pytest -v
```

Deberías ver todos los tests en verde (`PASSED`).

---

## 9. Preguntas frecuentes

**¿Puedo correrlo varias veces sin que se dupliquen los datos?**
Sí. Si intentas importar una referencia que ya existe en el sistema interno,
el programa la omite y te avisa en el detalle de errores/avisos. Cada vez que
ejecutas `POST /api/reconciliation/run` (o el script), los resultados de
conciliación anteriores se reemplazan por los nuevos.

**¿Dónde quedan guardados mis datos?**
En un archivo `reconciliation.db` que se crea automáticamente dentro de la
carpeta del proyecto. Es una base de datos SQLite: un solo archivo, sin
necesidad de instalar ningún motor de base de datos.

**¿Puedo borrar todo y empezar de nuevo?**
Sí, simplemente borra el archivo `reconciliation.db` y vuelve a correr el
script o la API; se recreará vacío.

**¿Y si mi archivo tiene columnas con otros nombres?**
Agrega el nombre que usas a la lista `COLUMN_ALIASES` en
`app/services/ingestion.py`, o renombra la columna en tu archivo antes de
importarlo.
