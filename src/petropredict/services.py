"""Servicios de dominio: ingesta de lecturas, tendencia y salud del equipo."""

from __future__ import annotations

import numpy as np
from sqlalchemy.orm import Session

from . import ml
from .config import ANOMALY_THRESHOLD, TEMPERATURE_LIMIT, VIBRATION_LIMIT
from .models import Alert, Equipment, SensorReading


def vibration_trend(db: Session, equipo_id: int, limit: int = 10) -> float:
    """Pendiente de la vibración (mm/s por hora) con las últimas lecturas."""
    lecturas = (
        db.query(SensorReading)
        .filter(SensorReading.equipo_id == equipo_id)
        .order_by(SensorReading.timestamp.desc())
        .limit(limit)
        .all()
    )
    if len(lecturas) < 2:
        return 0.0
    lecturas = sorted(lecturas, key=lambda r: r.horas_operacion)
    horas = np.asarray([r.horas_operacion for r in lecturas], dtype=float)
    vibraciones = np.asarray([r.vibracion_rms for r in lecturas], dtype=float)
    if horas[-1] == horas[0]:
        return 0.0
    return float(np.polyfit(horas, vibraciones, 1)[0])


def _severidad(
    anomaly_score: float,
    vibracion: float,
    temperatura: float,
) -> tuple[str | None, str]:
    """Devuelve (severidad, motivo) o (None, '') si no hay alerta."""
    if anomaly_score >= 0.85 or vibracion >= VIBRATION_LIMIT:
        return "critica", (
            f"Vibración {vibracion:.2f} mm/s o puntuación de anomalía "
            f"{anomaly_score:.2f} en nivel crítico"
        )
    if anomaly_score >= 0.7 or vibracion >= 4.5 or temperatura >= TEMPERATURE_LIMIT:
        return "alta", (
            f"Vibración {vibracion:.2f} mm/s, temperatura {temperatura:.1f} °C "
            f"o anomalía {anomaly_score:.2f} fuera de rango"
        )
    if anomaly_score >= ANOMALY_THRESHOLD or vibracion >= 4.0 or temperatura >= 80.0:
        return "media", (
            f"Posible degradación: vibración {vibracion:.2f} mm/s, "
            f"temperatura {temperatura:.1f} °C, anomalía {anomaly_score:.2f}"
        )
    return None, ""


def ingest_reading(
    db: Session, equipo: Equipment, datos: dict
) -> tuple[SensorReading, Alert | None]:
    """Guarda una lectura, calcula su anomalía y crea una alerta si aplica."""
    tendencia = vibration_trend(db, equipo.id)
    detector = ml.get_detector()
    score = detector.anomaly_score(
        datos["vibracion_rms"],
        datos["temperatura"],
        datos["presion"],
        tendencia,
        vibracion_nominal=equipo.vibracion_nominal,
        temperatura_nominal=equipo.temperatura_nominal,
        presion_nominal=equipo.presion_nominal,
    )
    lectura = SensorReading(
        equipo_id=equipo.id,
        vibracion_rms=datos["vibracion_rms"],
        temperatura=datos["temperatura"],
        presion=datos["presion"],
        horas_operacion=datos["horas_operacion"],
        anomaly_score=score,
        es_anomalia=detector.is_anomaly(score, ANOMALY_THRESHOLD),
    )
    db.add(lectura)
    db.commit()
    db.refresh(lectura)

    severidad, mensaje = _severidad(
        score, datos["vibracion_rms"], datos["temperatura"]
    )
    alerta = None
    if severidad is not None:
        alerta = Alert(
            equipo_id=equipo.id,
            lectura_id=lectura.id,
            severidad=severidad,
            mensaje=mensaje,
        )
        db.add(alerta)
        db.commit()
        db.refresh(alerta)
    return lectura, alerta


def equipment_health(db: Session, equipo: Equipment) -> dict:
    """Salud actual del equipo: puntuación, estado, RUL y alertas activas."""
    lecturas = (
        db.query(SensorReading)
        .filter(SensorReading.equipo_id == equipo.id)
        .order_by(SensorReading.timestamp.desc())
        .limit(20)
        .all()
    )
    alertas_activas = (
        db.query(Alert)
        .filter(Alert.equipo_id == equipo.id, Alert.resuelta.is_(False))
        .count()
    )
    if not lecturas:
        return {
            "equipo_id": equipo.id,
            "salud": 100.0,
            "estado": "sin_datos",
            "rul_horas": None,
            "riesgo": "bajo",
            "tendencia_vibracion": 0.0,
            "anomaly_score": None,
            "ultima_lectura": None,
            "alertas_activas": alertas_activas,
        }
    ultima = lecturas[0]
    historial = sorted(lecturas, key=lambda r: r.horas_operacion)
    rul = ml.estimate_rul(
        [r.horas_operacion for r in historial],
        [r.vibracion_rms for r in historial],
    )
    salud = ml.health_score(
        ultima.vibracion_rms,
        ultima.temperatura,
        ultima.presion,
        equipo.presion_nominal,
        ultima.anomaly_score,
        rul["tendencia"],
    )
    if rul["riesgo"] == "critico" or salud < 50:
        estado = "critico"
    elif salud < 80 or rul["riesgo"] in ("alto", "medio"):
        estado = "atencion"
    else:
        estado = "saludable"
    return {
        "equipo_id": equipo.id,
        "salud": salud,
        "estado": estado,
        "rul_horas": rul["rul_horas"],
        "riesgo": rul["riesgo"],
        "tendencia_vibracion": rul["tendencia"],
        "anomaly_score": ultima.anomaly_score,
        "ultima_lectura": ultima,
        "alertas_activas": alertas_activas,
    }
