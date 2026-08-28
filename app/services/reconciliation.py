"""
Motor de conciliación.

Compara las transacciones del sistema interno contra las del banco, usando
el identificador ya normalizado, y clasifica cada una en un estado:

    MATCH               -> misma referencia, mismo monto
    AMOUNT_DIFFERENCE   -> misma referencia, monto distinto
    MISSING_IN_BANK     -> existe en el sistema interno pero no en el banco
    MISSING_INTERNAL    -> existe en el banco pero no en el sistema interno
    DUPLICATE           -> la referencia aparece más de una vez en una fuente
"""

from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models import Transaction, BankTransaction, ReconciliationResult, ReconciliationRun
from app.services.audit import log_action

STATUS_MATCH = "MATCH"
STATUS_AMOUNT_DIFFERENCE = "AMOUNT_DIFFERENCE"
STATUS_MISSING_IN_BANK = "MISSING_IN_BANK"
STATUS_MISSING_INTERNAL = "MISSING_INTERNAL"
STATUS_DUPLICATE = "DUPLICATE"

AAA_TOLERANCE = Decimal("0.00")  # tolerancia permitida entre montos (ajustable)


def classify(internal_amount, bank_amount) -> str:
    """Lógica pura de clasificación, útil para tests unitarios rápidos."""
    if internal_amount is not None and bank_amount is None:
        return STATUS_MISSING_IN_BANK
    if internal_amount is None and bank_amount is not None:
        return STATUS_MISSING_INTERNAL
    if abs(Decimal(internal_amount) - Decimal(bank_amount)) <= AAA_TOLERANCE:
        return STATUS_MATCH
    return STATUS_AMOUNT_DIFFERENCE


def run_reconciliation(db: Session, triggered_by: str = "manual") -> dict:
    """
    Ejecuta la conciliación completa:
      1. Limpia resultados anteriores.
      2. Agrupa transacciones internas y bancarias por referencia normalizada.
      3. Detecta duplicados dentro de cada fuente.
      4. Compara una a una y guarda el resultado.
      5. Deja un registro en `reconciliation_runs` para auditoría (quién/qué
         disparó la corrida: manual, api, cli, n8n, make, power_automate).
    """
    run = ReconciliationRun(started_at=datetime.utcnow(), triggered_by=triggered_by, status="SUCCESS")
    db.add(run)
    db.commit()
    db.refresh(run)

    db.query(ReconciliationResult).delete()
    db.commit()

    try:
        summary = _do_reconciliation(db)
    except Exception as exc:  # noqa: BLE001 - queremos capturar cualquier fallo y dejarlo auditado
        run.status = "FAILED"
        run.error_message = str(exc)
        run.finished_at = datetime.utcnow()
        db.commit()
        log_action(db, process="reconciliation", action="Ejecución de conciliación",
                   status="ERROR", message=str(exc), triggered_by=triggered_by)
        raise

    run.finished_at = datetime.utcnow()
    run.total_records = summary["total"]
    run.matched = summary["matched"]
    run.missing_in_bank = summary["missing_in_bank"]
    run.missing_internal = summary["missing_internal"]
    run.amount_difference = summary["amount_difference"]
    run.duplicates = summary["duplicates"]
    db.commit()

    log_action(
        db, process="reconciliation", action="Ejecución de conciliación",
        status="SUCCESS",
        message=(
            f"total={summary['total']} matched={summary['matched']} "
            f"missing_in_bank={summary['missing_in_bank']} missing_internal={summary['missing_internal']} "
            f"amount_difference={summary['amount_difference']} duplicates={summary['duplicates']}"
        ),
        triggered_by=triggered_by,
    )

    summary["run_id"] = run.id
    return summary


def _do_reconciliation(db: Session) -> dict:
    """Lógica pura de comparación (separada para poder envolverla en try/except arriba)."""
    internal_txs = db.query(Transaction).all()
    bank_txs = db.query(BankTransaction).all()

    internal_by_ref: dict[str, list[Transaction]] = {}
    for tx in internal_txs:
        internal_by_ref.setdefault(tx.transaction_id_normalized, []).append(tx)

    bank_by_ref: dict[str, list[BankTransaction]] = {}
    for tx in bank_txs:
        bank_by_ref.setdefault(tx.bank_reference_normalized, []).append(tx)

    all_refs = set(internal_by_ref.keys()) | set(bank_by_ref.keys())

    summary = {
        "total": 0,
        "matched": 0,
        "missing_in_bank": 0,
        "missing_internal": 0,
        "amount_difference": 0,
        "duplicates": 0,
    }

    for ref in sorted(all_refs):
        internal_group = internal_by_ref.get(ref, [])
        bank_group = bank_by_ref.get(ref, [])
        summary["total"] += 1

        # Duplicados: la misma referencia aparece más de una vez en cualquiera de las fuentes.
        if len(internal_group) > 1 or len(bank_group) > 1:
            db.add(ReconciliationResult(
                transaction_id=internal_group[0].id if internal_group else None,
                bank_transaction_id=bank_group[0].id if bank_group else None,
                reference=ref,
                status=STATUS_DUPLICATE,
                expected_amount=internal_group[0].amount if internal_group else None,
                actual_amount=bank_group[0].amount if bank_group else None,
                difference=None,
            ))
            summary["duplicates"] += 1
            continue

        internal_tx = internal_group[0] if internal_group else None
        bank_tx = bank_group[0] if bank_group else None

        internal_amount = internal_tx.amount if internal_tx else None
        bank_amount = bank_tx.amount if bank_tx else None

        status = classify(internal_amount, bank_amount)
        difference = None
        if internal_amount is not None and bank_amount is not None:
            difference = Decimal(internal_amount) - Decimal(bank_amount)

        db.add(ReconciliationResult(
            transaction_id=internal_tx.id if internal_tx else None,
            bank_transaction_id=bank_tx.id if bank_tx else None,
            reference=ref,
            status=status,
            expected_amount=internal_amount,
            actual_amount=bank_amount,
            difference=difference,
        ))

        if status == STATUS_MATCH:
            summary["matched"] += 1
        elif status == STATUS_MISSING_IN_BANK:
            summary["missing_in_bank"] += 1
        elif status == STATUS_MISSING_INTERNAL:
            summary["missing_internal"] += 1
        elif status == STATUS_AMOUNT_DIFFERENCE:
            summary["amount_difference"] += 1

    db.commit()
    return summary
