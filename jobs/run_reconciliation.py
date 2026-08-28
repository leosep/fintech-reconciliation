"""
Script de demostración "todo en uno".

Este script NO requiere levantar la API. Sirve para probar el proyecto en
30 segundos: importa los archivos de ejemplo (o los que le indiques),
ejecuta la conciliación y genera el reporte Excel.

Uso básico (usa los archivos de ejemplo incluidos en data/input/):

    python jobs/run_reconciliation.py

Uso con tus propios archivos:

    python jobs/run_reconciliation.py --internal ruta/interno.csv --bank ruta/banco.csv
"""

import argparse
import os
import sys

# Permite ejecutar el script directamente con `python jobs/run_reconciliation.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, init_db
from app.services.ingestion import import_internal_transactions, import_bank_transactions
from app.services.reconciliation import run_reconciliation
from app.services.report import generate_excel_report

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_INTERNAL = os.path.join(BASE_DIR, "data", "input", "internal_transactions.csv")
DEFAULT_BANK = os.path.join(BASE_DIR, "data", "input", "bank_transactions.csv")


def main():
    parser = argparse.ArgumentParser(description="Ejecuta el proceso completo de conciliación.")
    parser.add_argument("--internal", default=DEFAULT_INTERNAL, help="Ruta al CSV/Excel del sistema interno")
    parser.add_argument("--bank", default=DEFAULT_BANK, help="Ruta al CSV/Excel del banco/procesador")
    args = parser.parse_args()

    print("=" * 70)
    print(" FINTECH RECONCILIATION - Ejecución de demostración")
    print("=" * 70)

    init_db()
    db = SessionLocal()

    try:
        print(f"\n[1/4] Importando transacciones internas desde: {args.internal}")
        internal_summary = import_internal_transactions(db, args.internal, triggered_by="cli")
        print(f"      Leídas: {internal_summary['rows_read']} | Importadas: {internal_summary['rows_imported']} | Rechazadas: {internal_summary['rows_rejected']}")
        for err in internal_summary["errors"]:
            print(f"      ! {err}")

        print(f"\n[2/4] Importando transacciones bancarias desde: {args.bank}")
        bank_summary = import_bank_transactions(db, args.bank, triggered_by="cli")
        print(f"      Leídas: {bank_summary['rows_read']} | Importadas: {bank_summary['rows_imported']} | Rechazadas: {bank_summary['rows_rejected']}")
        for err in bank_summary["errors"]:
            print(f"      ! {err}")

        print("\n[3/4] Ejecutando motor de conciliación...")
        result = run_reconciliation(db, triggered_by="cli")
        print(f"      Total revisadas:      {result['total']}")
        print(f"      MATCH:                {result['matched']}")
        print(f"      MISSING_IN_BANK:      {result['missing_in_bank']}")
        print(f"      MISSING_INTERNAL:     {result['missing_internal']}")
        print(f"      AMOUNT_DIFFERENCE:    {result['amount_difference']}")
        print(f"      DUPLICATE:            {result['duplicates']}")

        print("\n[4/4] Generando reporte Excel...")
        report_path = generate_excel_report(db)
        print(f"      Reporte generado en: {report_path}")

        print("\n" + "=" * 70)
        print(" LISTO. Abre el archivo Excel para ver el detalle de excepciones.")
        print("=" * 70)
    finally:
        db.close()


if __name__ == "__main__":
    main()
