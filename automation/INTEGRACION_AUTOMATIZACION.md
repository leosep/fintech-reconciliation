# Integración con Make / n8n / Power Automate

Este proyecto expone **un solo endpoint "todo en uno"** pensado exactamente
para ser llamado desde herramientas de automatización low-code:

```
POST /api/automation/run-pipeline
```

En una sola llamada HTTP:

1. Importa el archivo del sistema interno.
2. Importa el archivo del banco/procesador.
3. Ejecuta el motor de conciliación.
4. Genera el reporte Excel.
5. Devuelve un JSON con el resumen completo + la URL para descargar el Excel.
6. Deja todo registrado en la bitácora de auditoría (`/api/audit/log`) y en
   el historial de corridas (`/api/reconciliation/runs`), incluyendo qué
   herramienta disparó el proceso (`n8n`, `make`, `power_automate`, etc. vía
   el parámetro `triggered_by`).

Esto reemplaza el flujo manual típico:

```
1. Descargar Excel del banco
2. Abrir Excel
3. Copiar datos
4. Abrir otro archivo
5. Usar VLOOKUP
6. Comparar a mano
7. Encontrar diferencias
8. Armar otro Excel
9. Enviar el email
```

por un solo llamado HTTP disparado automáticamente todos los días.

---

## 1. Con n8n

Se incluye un workflow de ejemplo listo para importar:
**`automation/n8n_workflow_example.json`**

Flujo que arma:

```
Cron (7:00 AM)
   │
   ├── Leer archivo interno
   └── Leer archivo del banco
        │
        ▼
HTTP Request → POST /api/automation/run-pipeline
   (multipart/form-data: internal_file, bank_file)
        │
        ▼
   IF ¿hay excepciones?
        │
   ┌────┴────┐
   ▼         ▼
 Sí        No
   │         │
Descargar   (nada)
reporte
   │
   ▼
Enviar email con el Excel adjunto
```

### Pasos para importarlo

1. Abre n8n → menú **Import from File** → selecciona `n8n_workflow_example.json`.
2. Ajusta el nodo **"Ejecutar pipeline de conciliación (API)"**:
   - Cambia `http://localhost:8000` por la URL real donde corre tu API
     (por ejemplo, la IP del servidor o tu dominio si la despliegas en la nube).
3. Ajusta los nodos **"Leer archivo interno"** / **"Leer archivo del banco"**
   con la ruta real donde llegan tus archivos (o reemplázalos por un nodo
   que lea de Gmail/Outlook/SFTP, según cómo te llegue el archivo del banco).
4. Configura el nodo de email con tus credenciales SMTP o de Gmail/Outlook.
5. Activa el workflow.

---

## 2. Con Make (antes Integromat)

Estructura equivalente usando módulos nativos de Make:

```
Watch emails (Gmail/Outlook)
   │
   ▼
Descargar adjuntos (Excel del banco)
   │
   ▼
HTTP → Make a request
   Método: POST
   URL: http://tu-servidor:8000/api/automation/run-pipeline?triggered_by=make
   Body type: multipart/form-data
   Campos: internal_file, bank_file
   │
   ▼
Router
   ├── (excepciones > 0) → Descargar Excel del report_download_url → Enviar email/Slack
   └── (sin excepciones) → Fin
```

Puntos clave al configurar el módulo **HTTP → Make a request** en Make:

- Content-Type: `multipart/form-data`.
- Cada archivo va como un "Data" item con su nombre de campo exacto
  (`internal_file` y `bank_file`) — deben coincidir con los nombres que
  espera el endpoint.
- La respuesta JSON incluye `reconciliation.amount_difference`,
  `reconciliation.missing_in_bank`, etc. — úsalos en el **Router** para
  decidir si notificar o no.

---

## 3. Con Power Automate

Estructura equivalente en un entorno más corporativo (Outlook/Teams/SharePoint):

```
Trigger: "Cuando llega un correo con adjunto" (Outlook)
   │
   ▼
Guardar adjunto en OneDrive/SharePoint
   │
   ▼
Acción HTTP (o "Invoke a REST API")
   Método: POST
   URI: http://tu-servidor:8000/api/automation/run-pipeline?triggered_by=power_automate
   Body: multipart/form-data con internal_file y bank_file
   │
   ▼
Condición: ¿reconciliation.amount_difference + missing_in_bank + missing_internal + duplicates > 0?
   │
   ├── Sí → Descargar Excel (GET a report_download_url) → Publicar en SharePoint → Notificar en Teams
   └── No → Fin
```

Nota: si tu organización no permite exponer la API públicamente, puedes
correr la API dentro de la misma red (on-premises data gateway de Power
Automate) o desplegarla en un servidor accesible solo internamente.

---

## 4. Referencia rápida de los campos de respuesta

Todas las herramientas de automatización reciben el mismo JSON al llamar
`/api/automation/run-pipeline`:

```json
{
  "internal_import": { "rows_read": 6, "rows_imported": 6, "rows_rejected": 0, "errors": [] },
  "bank_import":      { "rows_read": 7, "rows_imported": 7, "rows_rejected": 0, "errors": [] },
  "reconciliation": {
    "total": 7,
    "matched": 3,
    "missing_in_bank": 1,
    "missing_internal": 1,
    "amount_difference": 1,
    "duplicates": 1,
    "run_id": 1
  },
  "report_download_url": "/api/reports/excel/reconciliation_2026-08-27_163818.xlsx"
}
```

Usa `reconciliation.*` para decidir si notificar, y `report_download_url`
(concatenado con la URL base de tu API) para descargar el Excel y adjuntarlo
al correo/Teams/Slack.

## 5. Auditoría de lo que dispara cada herramienta

Cada llamada queda registrada. Puedes consultar en cualquier momento:

- `GET /api/reconciliation/runs` — historial de corridas, con quién la disparó
  (`manual`, `api`, `cli`, `n8n`, `make`, `power_automate`) y sus totales.
- `GET /api/audit/log` — bitácora detallada de cada importación y ejecución.

Esto responde la pregunta típica de un entorno financiero: **"¿qué pasó con
las transacciones de ayer, y quién/qué disparó ese proceso?"**
