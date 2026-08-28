"""
Ingestión de archivos CSV / Excel.

Lee un archivo, valida columnas obligatorias, normaliza cada fila y devuelve
una lista de diccionarios listos para insertar en base de datos, junto con
un resumen de filas rechazadas y sus motivos (para no perder trazabilidad).
"""

import os
import pandas as pd
from sqlalchemy.orm import Session

from app.models import Transaction, BankTransaction
from app.services.normalization import normalize_reference, normalize_amount, normalize_date
from app.services.audit import log_action

# Mapea posibles nombres de columna (en español o inglés) al nombre estándar interno.
COLUMN_ALIASES = {
    "transaction_id": "reference",
    "referencia": "reference",
    "reference": "reference",
    "bank_reference": "reference",
    "id": "reference",

    "amount": "amount",
    "monto": "amount",
    "importe": "amount",

    "date": "date",
    "fecha": "date",
    "transaction_date": "date",

    "customer": "customer",
    "cliente": "customer",

    "currency": "currency",
    "moneda": "currency",
}


def _read_file(file_path: str) -> pd.DataFrame:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        return pd.read_csv(file_path)
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(file_path)
    raise ValueError(f"Formato de archivo no soportado: {ext}")


def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={c: c.strip().lower() for c in df.columns})
    df = df.rename(columns={c: COLUMN_ALIASES.get(c, c) for c in df.columns})
    return df


def _parse_rows(df: pd.DataFrame):
    """Convierte cada fila del DataFrame en un dict normalizado o registra el error."""
    valid_rows = []
    errors = []

    required = {"reference", "amount", "date"}
    missing_cols = required - set(df.columns)
    if missing_cols:
        raise ValueError(
            f"Faltan columnas obligatorias: {sorted(missing_cols)}. "
            f"Columnas encontradas: {list(df.columns)}"
        )

    for idx, row in df.iterrows():
        raw_reference = row.get("reference")
        try:
            reference = normalize_reference(raw_reference)
            if not reference:
                raise ValueError("Referencia vacía")

            # Nota: si la misma referencia aparece más de una vez (dentro del
            # archivo o entre archivos), NO se rechaza aquí. Se importa tal
            # cual y es el motor de conciliación (app/services/reconciliation.py)
            # el que la marca como estado DUPLICATE, para que quede visible en
            # el reporte en vez de desaparecer silenciosamente en la importación.

            amount = normalize_amount(row.get("amount"))
            date = normalize_date(row.get("date"))
            customer = str(row.get("customer")).strip() if "customer" in df.columns and pd.notna(row.get("customer")) else None
            currency = str(row.get("currency")).strip().upper() if "currency" in df.columns and pd.notna(row.get("currency")) else "DOP"

            valid_rows.append({
                "raw_reference": str(raw_reference),
                "reference_normalized": reference,
                "amount": amount,
                "date": date,
                "customer": customer,
                "currency": currency,
            })
        except Exception as exc:  # noqa: BLE001 - queremos capturar cualquier error de fila y seguir
            errors.append(f"Fila {idx + 2}: {exc}")

    return valid_rows, errors


def import_internal_transactions(db: Session, file_path: str, triggered_by: str = "manual"):
    """Importa transacciones del sistema interno desde CSV/Excel."""
    df = _standardize_columns(_read_file(file_path))
    rows, errors = _parse_rows(df)

    imported = 0
    for row in rows:
        exists = db.query(Transaction).filter(
            Transaction.transaction_id_normalized == row["reference_normalized"]
        ).first()
        if exists:
            errors.append(f"Referencia ya existe en base de datos, se omite: {row['raw_reference']}")
            continue

        db.add(Transaction(
            transaction_id=row["raw_reference"],
            transaction_id_normalized=row["reference_normalized"],
            customer=row["customer"],
            amount=row["amount"],
            currency=row["currency"],
            transaction_date=row["date"],
        ))
        imported += 1

    db.commit()

    summary = {
        "file_name": os.path.basename(file_path),
        "rows_read": len(df),
        "rows_imported": imported,
        "rows_rejected": len(df) - imported,
        "errors": errors,
    }
    log_action(
        db, process="import_internal", action=f"Importado {summary['file_name']}",
        status="WARNING" if errors else "SUCCESS",
        message=f"Leídas={summary['rows_read']} Importadas={imported} Rechazadas={summary['rows_rejected']}",
        triggered_by=triggered_by,
    )
    return summary


def import_bank_transactions(db: Session, file_path: str, triggered_by: str = "manual"):
    """Importa transacciones del banco/procesador desde CSV/Excel."""
    df = _standardize_columns(_read_file(file_path))
    rows, errors = _parse_rows(df)

    imported = 0
    for row in rows:
        db.add(BankTransaction(
            bank_reference=row["raw_reference"],
            bank_reference_normalized=row["reference_normalized"],
            amount=row["amount"],
            currency=row["currency"],
            transaction_date=row["date"],
        ))
        imported += 1

    db.commit()

    summary = {
        "file_name": os.path.basename(file_path),
        "rows_read": len(df),
        "rows_imported": imported,
        "rows_rejected": len(df) - imported,
        "errors": errors,
    }
    log_action(
        db, process="import_bank", action=f"Importado {summary['file_name']}",
        status="WARNING" if errors else "SUCCESS",
        message=f"Leídas={summary['rows_read']} Importadas={imported} Rechazadas={summary['rows_rejected']}",
        triggered_by=triggered_by,
    )
    return summary
