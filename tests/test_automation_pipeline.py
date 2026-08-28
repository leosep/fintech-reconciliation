import os
from fastapi.testclient import TestClient

from app.main import app

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INTERNAL_FILE = os.path.join(BASE_DIR, "data", "input", "internal_transactions.csv")
BANK_FILE = os.path.join(BASE_DIR, "data", "input", "bank_transactions.csv")


def test_automation_pipeline_end_to_end():
    """
    Simula exactamente lo que haría un nodo HTTP Request de n8n/Make/Power
    Automate: una sola llamada que importa ambos archivos, concilia y
    devuelve la URL del reporte.
    """
    with TestClient(app) as client:
        with open(INTERNAL_FILE, "rb") as f1, open(BANK_FILE, "rb") as f2:
            response = client.post(
                "/api/automation/run-pipeline",
                files={
                    "internal_file": ("internal_transactions.csv", f1, "text/csv"),
                    "bank_file": ("bank_transactions.csv", f2, "text/csv"),
                },
                params={"triggered_by": "n8n"},
            )

        assert response.status_code == 200
        body = response.json()

        assert body["internal_import"]["rows_imported"] > 0
        assert body["bank_import"]["rows_imported"] > 0
        assert body["reconciliation"]["total"] > 0
        assert "report_download_url" in body

        # El reporte debe poder descargarse inmediatamente después.
        report_response = client.get(body["report_download_url"])
        assert report_response.status_code == 200
        assert len(report_response.content) > 0

        # La corrida debe quedar auditada con el origen correcto.
        runs = client.get("/api/reconciliation/runs").json()
        assert any(r["triggered_by"] == "n8n" for r in runs)

        audit = client.get("/api/audit/log").json()
        assert any(a["process"] == "automation" for a in audit)
