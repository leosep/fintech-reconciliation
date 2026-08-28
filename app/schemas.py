from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class TransactionOut(BaseModel):
    id: int
    transaction_id: str
    customer: Optional[str] = None
    amount: float
    currency: str
    transaction_date: datetime

    class Config:
        from_attributes = True


class BankTransactionOut(BaseModel):
    id: int
    bank_reference: str
    amount: float
    currency: str
    transaction_date: datetime

    class Config:
        from_attributes = True


class ReconciliationResultOut(BaseModel):
    id: int
    reference: str
    status: str
    expected_amount: Optional[float] = None
    actual_amount: Optional[float] = None
    difference: Optional[float] = None
    reconciled_at: datetime

    class Config:
        from_attributes = True


class ImportSummary(BaseModel):
    file_name: str
    rows_read: int
    rows_imported: int
    rows_rejected: int
    errors: list[str] = []


class ReconciliationSummary(BaseModel):
    total: int
    matched: int
    missing_in_bank: int
    missing_internal: int
    amount_difference: int
    duplicates: int
    run_id: Optional[int] = None


class ReconciliationRunOut(BaseModel):
    id: int
    started_at: datetime
    finished_at: Optional[datetime] = None
    triggered_by: str
    total_records: int
    matched: int
    missing_in_bank: int
    missing_internal: int
    amount_difference: int
    duplicates: int
    status: str
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class AuditLogOut(BaseModel):
    id: int
    timestamp: datetime
    process: str
    action: str
    triggered_by: str
    status: str
    message: Optional[str] = None

    class Config:
        from_attributes = True


class AutomationPipelineResult(BaseModel):
    """
    Resultado del endpoint 'todo en uno' pensado para ser llamado desde
    Make, n8n o Power Automate: importa ambos archivos, concilia y deja
    el reporte listo para descargar.
    """
    internal_import: ImportSummary
    bank_import: ImportSummary
    reconciliation: ReconciliationSummary
    report_download_url: str
