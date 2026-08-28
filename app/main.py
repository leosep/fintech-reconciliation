"""
API principal - Fintech Reconciliation Automation Platform.

Para levantarla:

    uvicorn app.main:app --reload

Documentación interactiva automática en:

    http://127.0.0.1:8000/docs
"""

import os
import shutil
import tempfile

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.models import Transaction, BankTransaction, ReconciliationResult, ReconciliationRun, AuditLog
from app.schemas import (
    TransactionOut, BankTransactionOut, ReconciliationResultOut,
    ImportSummary, ReconciliationSummary, ReconciliationRunOut, AuditLogOut,
    AutomationPipelineResult,
)
from app.services.ingestion import import_internal_transactions, import_bank_transactions
from app.services.reconciliation import run_reconciliation
from app.services.report import generate_excel_report
from app.services.audit import log_action

app = FastAPI(
    title="Fintech Reconciliation Automation Platform",
    description="Conciliación automática de pagos entre sistema interno y banco/procesador.",
    version="1.0.0",
)


@app.on_event("startup")
def on_startup():
    init_db()


def _save_upload_to_temp(file: UploadFile) -> str:
    suffix = os.path.splitext(file.filename)[1] or ".csv"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        return tmp.name


@app.get("/", tags=["Info"])
def root():
    return {
        "message": "Fintech Reconciliation Automation Platform",
        "docs": "/docs",
    }


# ---------------------------------------------------------------------------
# Importación de archivos
# ---------------------------------------------------------------------------

@app.post("/api/import/internal", response_model=ImportSummary, tags=["Importación"])
def import_internal(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Importa un CSV/Excel de transacciones del sistema interno."""
    tmp_path = _save_upload_to_temp(file)
    try:
        result = import_internal_transactions(db, tmp_path, triggered_by="api")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        os.remove(tmp_path)
    return result


@app.post("/api/import/bank", response_model=ImportSummary, tags=["Importación"])
def import_bank(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Importa un CSV/Excel de transacciones del banco/procesador."""
    tmp_path = _save_upload_to_temp(file)
    try:
        result = import_bank_transactions(db, tmp_path, triggered_by="api")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        os.remove(tmp_path)
    return result


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

@app.get("/api/transactions", response_model=list[TransactionOut], tags=["Consultas"])
def list_transactions(db: Session = Depends(get_db)):
    return db.query(Transaction).all()


@app.get("/api/transactions/bank", response_model=list[BankTransactionOut], tags=["Consultas"])
def list_bank_transactions(db: Session = Depends(get_db)):
    return db.query(BankTransaction).all()


# ---------------------------------------------------------------------------
# Conciliación
# ---------------------------------------------------------------------------

@app.post("/api/reconciliation/run", response_model=ReconciliationSummary, tags=["Conciliación"])
def reconciliation_run(triggered_by: str = "api", db: Session = Depends(get_db)):
    """
    Ejecuta el motor de conciliación sobre todo lo importado hasta ahora.

    `triggered_by` queda registrado en `reconciliation_runs` y en la bitácora
    de auditoría. Úsalo, por ejemplo, para distinguir corridas manuales de
    corridas disparadas por n8n/Make/Power Automate: `?triggered_by=n8n`.
    """
    return run_reconciliation(db, triggered_by=triggered_by)


@app.get("/api/reconciliation/results", response_model=list[ReconciliationResultOut], tags=["Conciliación"])
def reconciliation_results(db: Session = Depends(get_db)):
    return db.query(ReconciliationResult).all()


@app.get("/api/reconciliation/exceptions", response_model=list[ReconciliationResultOut], tags=["Conciliación"])
def reconciliation_exceptions(db: Session = Depends(get_db)):
    return db.query(ReconciliationResult).filter(ReconciliationResult.status != "MATCH").all()


@app.get("/api/reconciliation/runs", response_model=list[ReconciliationRunOut], tags=["Conciliación"])
def reconciliation_runs(db: Session = Depends(get_db)):
    """
    Historial de corridas de conciliación (auditoría). Responde a la pregunta
    '¿qué pasó con las transacciones de ayer?'.
    """
    return db.query(ReconciliationRun).order_by(ReconciliationRun.id.desc()).all()


# ---------------------------------------------------------------------------
# Reportes
# ---------------------------------------------------------------------------

@app.get("/api/reports/excel", tags=["Reportes"])
def reports_excel(db: Session = Depends(get_db)):
    """Genera y descarga un reporte Excel con el resumen y las excepciones."""
    file_path = generate_excel_report(db)
    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=os.path.basename(file_path),
    )


@app.get("/api/reports/excel/{file_name}", tags=["Reportes"])
def download_report_by_name(file_name: str):
    """Descarga un reporte Excel ya generado por su nombre de archivo."""
    from app.services.report import OUTPUT_DIR
    file_path = os.path.join(OUTPUT_DIR, file_name)
    if not os.path.isfile(file_path) or not file_name.endswith(".xlsx"):
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=file_name,
    )


# ---------------------------------------------------------------------------
# Auditoría
# ---------------------------------------------------------------------------

@app.get("/api/audit/log", response_model=list[AuditLogOut], tags=["Auditoría"])
def audit_log(db: Session = Depends(get_db)):
    """Bitácora completa de importaciones, conciliaciones y automatizaciones."""
    return db.query(AuditLog).order_by(AuditLog.id.desc()).all()


# ---------------------------------------------------------------------------
# Automatización (Make / n8n / Power Automate)
# ---------------------------------------------------------------------------
#
# Este endpoint está pensado para ser llamado por una herramienta low-code
# (nodo "HTTP Request" en n8n, módulo "HTTP" en Make, conector "HTTP" en
# Power Automate) con dos archivos adjuntos. Hace en una sola llamada lo
# que normalmente serían 3-4 pasos manuales: importar ambos archivos,
# conciliar, y dejar el reporte Excel listo para descargar o reenviar
# por correo/Teams/Slack desde el propio workflow de automatización.
#
# Ejemplo de uso típico en n8n:
#   Cron (7:00 AM) -> Leer archivo del banco -> HTTP Request a este endpoint
#   -> IF (¿hay excepciones?) -> Enviar email/Teams con el reporte adjunto
#
# Ver /automation/n8n_workflow_example.json para un workflow importable.

@app.post("/api/automation/run-pipeline", response_model=AutomationPipelineResult, tags=["Automatización"])
def automation_run_pipeline(
    internal_file: UploadFile = File(..., description="Archivo CSV/Excel del sistema interno"),
    bank_file: UploadFile = File(..., description="Archivo CSV/Excel del banco/procesador"),
    triggered_by: str = "automation",
    db: Session = Depends(get_db),
):
    """
    Endpoint 'todo en uno': importa ambos archivos, ejecuta la conciliación
    y genera el reporte Excel, en una sola llamada HTTP. Ideal para Make,
    n8n o Power Automate.
    """
    internal_tmp = _save_upload_to_temp(internal_file)
    bank_tmp = _save_upload_to_temp(bank_file)

    try:
        internal_summary = import_internal_transactions(db, internal_tmp, triggered_by=triggered_by)
        bank_summary = import_bank_transactions(db, bank_tmp, triggered_by=triggered_by)
        reconciliation_summary = run_reconciliation(db, triggered_by=triggered_by)
        report_path = generate_excel_report(db)

        log_action(
            db, process="automation", action="Pipeline completo ejecutado",
            status="SUCCESS", triggered_by=triggered_by,
            message=f"Reporte generado: {os.path.basename(report_path)}",
        )
    except Exception as exc:
        log_action(
            db, process="automation", action="Pipeline completo falló",
            status="ERROR", triggered_by=triggered_by, message=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        os.remove(internal_tmp)
        os.remove(bank_tmp)

    return {
        "internal_import": internal_summary,
        "bank_import": bank_summary,
        "reconciliation": reconciliation_summary,
        "report_download_url": f"/api/reports/excel/{os.path.basename(report_path)}",
    }
