from __future__ import annotations

import configparser
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.ini"


def load_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            "No existe config.ini. Copia config.ini.example a config.ini y ajusta la IP y credenciales."
        )
    config.read(CONFIG_PATH)
    return config


def get_database_url() -> str:
    config = load_config()
    section = config["database"]
    url = section.get("url")
    if url:
        return url

    host = section.get("host", "127.0.0.1")
    port = section.get("port", "5432")
    user = section.get("user", "postgres")
    password = section.get("password", "postgres")
    name = section.get("name", "escuadron_horas")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


def get_engine():
    url = get_database_url()
    engine_kwargs = {"echo": False, "future": True}
    if url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **engine_kwargs)


SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    if str(engine.url).startswith("sqlite"):
        with engine.begin() as connection:
            table_exists = connection.execute(
                text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='registros_vuelo'")
            ).fetchone()
            if not table_exists:
                return

            columns = {
                row[1]: row
                for row in connection.execute(text("PRAGMA table_info(registros_vuelo)")).fetchall()
            }

            if "grado_piloto" not in columns:
                connection.execute(
                    text(
                        "ALTER TABLE registros_vuelo ADD COLUMN grado_piloto VARCHAR(50) NOT NULL DEFAULT 'Alférez'"
                    )
                )
                columns["grado_piloto"] = True

            needs_rebuild = (
                "fecha_vuelo" not in columns
                or "horas_vuelo" not in columns
                or "hora_salida" in columns and columns["hora_salida"][3] == 1
                or "hora_llegada" in columns and columns["hora_llegada"][3] == 1
            )

            if not needs_rebuild:
                return

            connection.execute(text("ALTER TABLE registros_vuelo RENAME TO registros_vuelo_old"))
            connection.execute(
                text(
                    """
                    CREATE TABLE registros_vuelo (
                        id INTEGER NOT NULL,
                        id_mision INTEGER NOT NULL,
                        id_aeronave INTEGER NOT NULL,
                        id_piloto INTEGER NOT NULL,
                        id_copiloto INTEGER,
                        origen VARCHAR(100) NOT NULL,
                        destino VARCHAR(100) NOT NULL,
                        fecha_vuelo DATE NOT NULL,
                        horas_vuelo VARCHAR(10) NOT NULL DEFAULT '00:00',
                        hora_salida DATETIME,
                        hora_llegada DATETIME,
                        tiempo_total_minutos FLOAT NOT NULL DEFAULT 0.0,
                        horas_diurnas FLOAT NOT NULL DEFAULT 0.0,
                        horas_nocturnas FLOAT NOT NULL DEFAULT 0.0,
                        horas_nvg FLOAT NOT NULL DEFAULT 0.0,
                        horas_instrumentos FLOAT NOT NULL DEFAULT 0.0,
                        PRIMARY KEY (id),
                        CHECK (tiempo_total_minutos >= 0),
                        CHECK (horas_diurnas >= 0),
                        CHECK (horas_nocturnas >= 0),
                        CHECK (horas_nvg >= 0),
                        CHECK (horas_instrumentos >= 0)
                    )
                    """
                )
            )

            old_columns = [
                "id", "id_mision", "id_aeronave", "id_piloto", "id_copiloto",
                "origen", "destino", "hora_salida", "hora_llegada",
                "tiempo_total_minutos", "horas_diurnas", "horas_nocturnas", "horas_nvg", "horas_instrumentos"
            ]
            select_cols = ", ".join(old_columns)
            legacy_date = "COALESCE(fecha_vuelo, date('2000-01-01'))"
            legacy_duration = "COALESCE(horas_vuelo, '00:00')"

            connection.execute(
                text(
                    f"""
                    INSERT INTO registros_vuelo (
                        id, id_mision, id_aeronave, id_piloto, id_copiloto,
                        origen, destino, fecha_vuelo, horas_vuelo,
                        hora_salida, hora_llegada,
                        tiempo_total_minutos, horas_diurnas, horas_nocturnas, horas_nvg, horas_instrumentos
                    )
                    SELECT
                        id, id_mision, id_aeronave, id_piloto, id_copiloto,
                        origen, destino, {legacy_date}, {legacy_duration},
                        hora_salida, hora_llegada,
                        tiempo_total_minutos, horas_diurnas, horas_nocturnas, horas_nvg, horas_instrumentos
                    FROM registros_vuelo_old
                    """
                )
            )
            connection.execute(text("DROP TABLE registros_vuelo_old"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection() -> bool:
    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
