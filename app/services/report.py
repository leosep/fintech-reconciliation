"""
Generación de reportes.

Produce un archivo Excel con dos hojas:
  - "Summary": totales por estado.
  - "Exceptions": el detalle de todo lo que NO fue un MATCH perfecto.
"""

import os
from datetime import datetime
import pandas as pd

from sqlalchemy.orm import Session
from app.models import ReconciliationResult

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "output"
)


def generate_excel_report(db: Session) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    results = db.query(ReconciliationResult).all()

    summary_counts = {}
    exception_rows = []

    for r in results:
        summary_counts[r.status] = summary_counts.get(r.status, 0) + 1
        if r.status != "MATCH":
            exception_rows.append({
                "Referencia": r.reference,
                "Estado": r.status,
                "Monto esperado": float(r.expected_amount) if r.expected_amount is not None else None,
                "Monto real": float(r.actual_amount) if r.actual_amount is not None else None,
                "Diferencia": float(r.difference) if r.difference is not None else None,
            })

    summary_df = pd.DataFrame(
        [{"Estado": k, "Cantidad": v} for k, v in summary_counts.items()] +
        [{"Estado": "TOTAL", "Cantidad": len(results)}]
    )
    exceptions_df = pd.DataFrame(exception_rows) if exception_rows else pd.DataFrame(
        columns=["Referencia", "Estado", "Monto esperado", "Monto real", "Diferencia"]
    )

    file_name = f"reconciliation_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.xlsx"
    file_path = os.path.join(OUTPUT_DIR, file_name)

    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        exceptions_df.to_excel(writer, sheet_name="Exceptions", index=False)

    return file_path
