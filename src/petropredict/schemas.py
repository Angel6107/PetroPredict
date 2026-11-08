"""Esquemas Pydantic v2 de la API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TipoEquipo(str, Enum):
    bomba_centrifuga = "bomba_centrifuga"
    compresor = "compresor"
    motor = "motor"


class EquipoCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    tipo: TipoEquipo
    ubicacion: str = ""
    vibracion_nominal: float = Field(default=2.8, gt=0)
    temperatura_nominal: float = Field(default=68.0)
    presion_nominal: float = Field(default=8.0, gt=0)


class EquipoOut(EquipoCreate):
    id: int
    creado_en: datetime

    model_config = ConfigDict(from_attributes=True)


class LecturaCreate(BaseModel):
    vibracion_rms: float = Field(ge=0, le=50, description="Vibración en mm/s RMS")
    temperatura: float = Field(ge=-20, le=200, description="Temperatura en °C")
    presion: float = Field(ge=0, le=50, description="Presión en bar")
    horas_operacion: float = Field(ge=0, description="Horas acumuladas de operación")


class AlertaOut(BaseModel):
    id: int
    equipo_id: int
    lectura_id: int | None
    severidad: str
    mensaje: str
    resuelta: bool
    creado_en: datetime

    model_config = ConfigDict(from_attributes=True)


class LecturaOut(BaseModel):
    id: int
    equipo_id: int
    timestamp: datetime
    vibracion_rms: float
    temperatura: float
    presion: float
    horas_operacion: float
    anomaly_score: float
    es_anomalia: bool

    model_config = ConfigDict(from_attributes=True)


class LecturaIngestResponse(BaseModel):
    lectura: LecturaOut
    anomaly_score: float
    es_anomalia: bool
    alerta: AlertaOut | None


class SaludOut(BaseModel):
    equipo_id: int
    salud: float
    estado: str
    rul_horas: float | None
    riesgo: str
    tendencia_vibracion: float
    anomaly_score: float | None
    ultima_lectura: LecturaOut | None
    alertas_activas: int
