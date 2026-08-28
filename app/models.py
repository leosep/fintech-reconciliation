"""
Modelos de base de datos (tablas).

Diseño:

    transactions            -> transacciones del sistema interno
    bank_transactions        -> transacciones reportadas por el banco/procesador
    reconciliation_results    -> resultado de comparar ambas fuentes
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Numeric, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship

from app.database import Base


class Transaction(Base):
    """Transacción registrada por el sistema interno de la empresa."""
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String(50), unique=True, index=True, nullable=False)
    transaction_id_normalized = Column(String(50), index=True, nullable=False)
    customer = Column(String(150), nullable=True)
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), default="DOP")
    transaction_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    results = relationship("ReconciliationResult", back_populates="transaction")


class BankTransaction(Base):
    """Transacción tal como la reporta el banco / procesador de pagos."""
    __tablename__ = "bank_transactions"

    id = Column(Integer, primary_key=True, index=True)
    bank_reference = Column(String(100), index=True, nullable=False)
    bank_reference_normalized = Column(String(100), index=True, nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), default="DOP")
    transaction_date = Column(DateTime, nullable=False)
    imported_at = Column(DateTime, default=datetime.utcnow)

    results = relationship("ReconciliationResult", back_populates="bank_transaction")


class ReconciliationResult(Base):
    """Resultado de conciliar una transacción interna contra el banco."""
    __tablename__ = "reconciliation_results"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)
    bank_transaction_id = Column(Integer, ForeignKey("bank_transactions.id"), nullable=True)

    reference = Column(String(100), index=True, nullable=False)
    status = Column(String(30), nullable=False)  # ver app/services/reconciliation.py
    expected_amount = Column(Numeric(18, 2), nullable=True)
    actual_amount = Column(Numeric(18, 2), nullable=True)
    difference = Column(Numeric(18, 2), nullable=True)
    reconciled_at = Column(DateTime, default=datetime.utcnow)

    transaction = relationship("Transaction", back_populates="results")
    bank_transaction = relationship("BankTransaction", back_populates="results")


class ReconciliationRun(Base):
    """
    Registro de cada ejecución del motor de conciliación.

    Pensado para responder la pregunta típica de un entorno financiero:
    "¿qué pasó con las transacciones de ayer?". Cada vez que se corre la
    conciliación (desde la API, el script de línea de comandos, o disparado
    por Make/n8n/Power Automate) queda un renglón aquí con los totales.
    """
    __tablename__ = "reconciliation_runs"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    triggered_by = Column(String(50), default="manual")  # manual | api | n8n | make | power_automate | cli
    total_records = Column(Integer, default=0)
    matched = Column(Integer, default=0)
    missing_in_bank = Column(Integer, default=0)
    missing_internal = Column(Integer, default=0)
    amount_difference = Column(Integer, default=0)
    duplicates = Column(Integer, default=0)
    status = Column(String(20), default="SUCCESS")  # SUCCESS | FAILED
    error_message = Column(String(500), nullable=True)


class AuditLog(Base):
    """
    Bitácora de auditoría: cada importación, ejecución de conciliación o
    disparo de automatización queda registrado con marca de tiempo.
    """
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    process = Column(String(50), nullable=False)   # import_internal | import_bank | reconciliation | automation
    action = Column(String(100), nullable=False)
    triggered_by = Column(String(50), default="manual")
    status = Column(String(20), default="SUCCESS")  # SUCCESS | ERROR | WARNING
    message = Column(String(1000), nullable=True)
