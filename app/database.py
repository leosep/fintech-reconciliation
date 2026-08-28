"""
Configuración de la base de datos.

Usamos SQLite porque el objetivo del proyecto es que funcione "out of the box"
sin instalar un motor de base de datos aparte. El diseño (SQLAlchemy ORM) es
el mismo que usarías contra PostgreSQL o SQL Server: si en el futuro quieres
migrar, solo cambias la variable DATABASE_URL.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = os.getenv(
    "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'reconciliation.db')}"
)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependencia de FastAPI: entrega una sesión de BD y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Crea todas las tablas si no existen todavía."""
    from app import models  # noqa: F401 (asegura que los modelos se registren)
    Base.metadata.create_all(bind=engine)
