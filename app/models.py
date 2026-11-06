from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    rol = Column(String(20), nullable=False, default="user")
    estado = Column(String(20), nullable=False, default="Activo")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PilotoTripulante(Base):
    __tablename__ = "pilotos_tripulantes"

    id = Column(Integer, primary_key=True, index=True)
    grado = Column(String(50), nullable=False)
    nombres = Column(String(100), nullable=False)
    apellidos = Column(String(100), nullable=False)
    identificacion = Column(String(50), unique=True, nullable=False, index=True)
    funcion_habitual = Column(String(100), nullable=False, default="Tripulante")
    estado = Column(String(20), nullable=False, default="Activo")

    certificaciones = relationship("PilotoCertificacion", back_populates="piloto")
    habilitaciones_aeronave = relationship("PilotoHabilitacionAeronave", back_populates="piloto", cascade="all, delete-orphan")
    registros_piloto = relationship(
        "RegistroVuelo",
        foreign_keys="RegistroVuelo.id_piloto",
        back_populates="piloto",
    )
    registros_copiloto = relationship(
        "RegistroVuelo",
        foreign_keys="RegistroVuelo.id_copiloto",
        back_populates="copiloto",
    )


class PilotoCertificacion(Base):
    __tablename__ = "pilotos_certificaciones"

    id = Column(Integer, primary_key=True, index=True)
    id_piloto = Column(Integer, ForeignKey("pilotos_tripulantes.id"), nullable=False)
    id_aeronave = Column(Integer, ForeignKey("aeronaves.id"), nullable=True)
    modelo_aeronave = Column(String(100), nullable=True)
    tipo_cualificacion = Column(String(80), nullable=False)
    nivel = Column(String(80), nullable=False, default="Tipo")
    estado = Column(String(20), nullable=False, default="Activo")
    observaciones = Column(Text, nullable=True)

    piloto = relationship("PilotoTripulante", back_populates="certificaciones")
    aeronave = relationship("Aeronave", back_populates="certificaciones")


class PilotoHabilitacionAeronave(Base):
    __tablename__ = "pilotos_habilitaciones_aeronave"

    id = Column(Integer, primary_key=True, index=True)
    id_piloto = Column(Integer, ForeignKey("pilotos_tripulantes.id"), nullable=False)
    tipo_aeronave = Column(String(80), nullable=False)

    piloto = relationship("PilotoTripulante", back_populates="habilitaciones_aeronave")


class Aeronave(Base):
    __tablename__ = "aeronaves"

    id = Column(Integer, primary_key=True, index=True)
    matricula = Column(String(30), unique=True, nullable=False, index=True)
    modelo = Column(String(80), nullable=False)
    horas_vuelo_iniciales = Column(Float, nullable=False, default=0.0)
    estado = Column(String(30), nullable=False, default="Servicial")

    certificaciones = relationship("PilotoCertificacion", back_populates="aeronave")
    registros = relationship("RegistroVuelo", back_populates="aeronave")


class Mision(Base):
    __tablename__ = "misiones"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(50), unique=True, nullable=False, index=True)
    tipo_mision = Column(String(80), nullable=False)
    fecha_salida = Column(Date, nullable=False)
    observaciones = Column(Text, nullable=True)

    registros = relationship("RegistroVuelo", back_populates="mision")


class RegistroVuelo(Base):
    __tablename__ = "registros_vuelo"

    id = Column(Integer, primary_key=True, index=True)
    id_mision = Column(Integer, ForeignKey("misiones.id"), nullable=False)
    id_aeronave = Column(Integer, ForeignKey("aeronaves.id"), nullable=False)
    id_piloto = Column(Integer, ForeignKey("pilotos_tripulantes.id"), nullable=False)
    id_copiloto = Column(Integer, ForeignKey("pilotos_tripulantes.id"), nullable=True)
    grado_piloto = Column(String(50), nullable=False, default="Alférez")

    origen = Column(String(100), nullable=False)
    destino = Column(String(100), nullable=False)
    fecha_vuelo = Column(Date, nullable=False)
    horas_vuelo = Column(String(10), nullable=False, default="00:00")
    hora_salida = Column(DateTime, nullable=True)
    hora_llegada = Column(DateTime, nullable=True)

    tiempo_total_minutos = Column(Float, nullable=False, default=0.0)
    horas_diurnas = Column(Float, nullable=False, default=0.0)
    horas_nocturnas = Column(Float, nullable=False, default=0.0)
    horas_nvg = Column(Float, nullable=False, default=0.0)
    horas_instrumentos = Column(Float, nullable=False, default=0.0)

    __table_args__ = (
        CheckConstraint("tiempo_total_minutos >= 0", name="ck_registro_tiempo_total_pos"),
        CheckConstraint("horas_diurnas >= 0", name="ck_registro_diurna_pos"),
        CheckConstraint("horas_nocturnas >= 0", name="ck_registro_nocturna_pos"),
        CheckConstraint("horas_nvg >= 0", name="ck_registro_nvg_pos"),
        CheckConstraint("horas_instrumentos >= 0", name="ck_registro_instr_pos"),
    )

    mision = relationship("Mision", back_populates="registros")
    aeronave = relationship("Aeronave", back_populates="registros")
    piloto = relationship(
        "PilotoTripulante",
        foreign_keys=[id_piloto],
        back_populates="registros_piloto",
    )
    copiloto = relationship(
        "PilotoTripulante",
        foreign_keys=[id_copiloto],
        back_populates="registros_copiloto",
    )
