"""Modelos de dominio: Equipo, SensorReading y Alert."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Equipment(Base):
    """Un equipo rotativo de la instalación: bomba, compresor o motor."""

    __tablename__ = "equipos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    ubicacion: Mapped[str] = mapped_column(String(120), default="")
    vibracion_nominal: Mapped[float] = mapped_column(Float, default=2.8)
    temperatura_nominal: Mapped[float] = mapped_column(Float, default=68.0)
    presion_nominal: Mapped[float] = mapped_column(Float, default=8.0)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    lecturas: Mapped[list["SensorReading"]] = relationship(
        "SensorReading", back_populates="equipo", cascade="all, delete-orphan"
    )
    alertas: Mapped[list["Alert"]] = relationship(
        "Alert", back_populates="equipo", cascade="all, delete-orphan"
    )


class SensorReading(Base):
    """Una lectura de sensores: vibración, temperatura, presión y horas de operación."""

    __tablename__ = "lecturas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    vibracion_rms: Mapped[float] = mapped_column(Float, nullable=False)
    temperatura: Mapped[float] = mapped_column(Float, nullable=False)
    presion: Mapped[float] = mapped_column(Float, nullable=False)
    horas_operacion: Mapped[float] = mapped_column(Float, nullable=False)
    anomaly_score: Mapped[float] = mapped_column(Float, default=0.0)
    es_anomalia: Mapped[bool] = mapped_column(Boolean, default=False)

    equipo: Mapped["Equipment"] = relationship("Equipment", back_populates="lecturas")


class Alert(Base):
    """Una alerta generada cuando una lectura es anómala o supera un límite."""

    __tablename__ = "alertas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"), nullable=False)
    lectura_id: Mapped[int | None] = mapped_column(ForeignKey("lecturas.id"), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    severidad: Mapped[str] = mapped_column(String(20), nullable=False)
    mensaje: Mapped[str] = mapped_column(String(500), nullable=False)
    resuelta: Mapped[bool] = mapped_column(Boolean, default=False)

    equipo: Mapped["Equipment"] = relationship("Equipment", back_populates="alertas")
