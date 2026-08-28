"""
Auditoría.

Un solo helper para dejar rastro de cada acción importante: importaciones,
corridas de conciliación, y disparos desde herramientas de automatización
(Make, n8n, Power Automate). Esto responde la pregunta típica de un entorno
financiero: "¿qué pasó con las transacciones de ayer?".
"""

from sqlalchemy.orm import Session
from app.models import AuditLog


def log_action(db: Session, process: str, action: str, status: str = "SUCCESS",
                message: str = None, triggered_by: str = "manual") -> AuditLog:
    entry = AuditLog(
        process=process,
        action=action,
        status=status,
        message=message,
        triggered_by=triggered_by,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
