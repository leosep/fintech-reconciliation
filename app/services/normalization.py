"""
Normalización de datos.

Los distintos sistemas (interno, banco, archivos Excel) casi nunca usan
exactamente el mismo formato para IDs, montos o fechas. Este módulo convierte
todo a un formato común ANTES de guardarlo en base de datos, para que el
motor de conciliación pueda comparar "manzanas con manzanas".
"""

import re
from decimal import Decimal, InvalidOperation
from datetime import datetime
import pandas as pd


def normalize_reference(value) -> str:
    """
    Normaliza un identificador de transacción.

    Ejemplos:
        "TX-001"   -> "TX001"
        " tx 001 " -> "TX001"
        "tx_001"   -> "TX001"
    """
    if value is None:
        return ""
    text = str(value).strip().upper()
    text = re.sub(r"[\s\-_]", "", text)
    return text


def normalize_amount(value) -> Decimal:
    """
    Normaliza un monto a Decimal con 2 posiciones decimales.

    Ejemplos:
        "RD$ 1,500.00" -> Decimal("1500.00")
        "1500"         -> Decimal("1500.00")
        1500.5         -> Decimal("1500.50")
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise ValueError("Monto vacío")

    if isinstance(value, (int, float, Decimal)):
        cleaned = str(value)
    else:
        cleaned = str(value)
        cleaned = re.sub(r"[^0-9.\-]", "", cleaned.replace(",", ""))

    if cleaned in ("", "-", "."):
        raise ValueError(f"Monto inválido: {value!r}")

    try:
        return Decimal(cleaned).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError(f"Monto inválido: {value!r}") from exc


def normalize_date(value) -> datetime:
    """
    Normaliza una fecha a datetime. Acepta strings en varios formatos comunes
    y objetos datetime/Timestamp de pandas.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise ValueError("Fecha vacía")

    if isinstance(value, datetime):
        return value

    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()

    text = str(value).strip()
    formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    # Último recurso: dejar que pandas intente inferir el formato.
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"Fecha inválida: {value!r}")
    return parsed.to_pydatetime()
