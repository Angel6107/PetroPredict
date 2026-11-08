"""API REST de PetroPredict."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

from . import ml, schemas, services
from .database import get_db, init_db
from .models import Alert, Equipment


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ml.get_detector()  # Precalienta el modelo al arrancar.
    yield


app = FastAPI(
    title="PetroPredict",
    version="0.1.0",
    description=(
        "Mantenimiento predictivo para bombas y compresores de instalaciones "
        "petroleras. Los datos de sensores son simulados."
    ),
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/equipos", response_model=schemas.EquipoOut, status_code=201)
def crear_equipo(payload: schemas.EquipoCreate, db: Session = Depends(get_db)):
    equipo = Equipment(**payload.model_dump())
    db.add(equipo)
    db.commit()
    db.refresh(equipo)
    return equipo


@app.get("/equipos", response_model=list[schemas.EquipoOut])
def listar_equipos(db: Session = Depends(get_db)):
    return db.query(Equipment).order_by(Equipment.id).all()


@app.get("/equipos/{equipo_id}", response_model=schemas.EquipoOut)
def obtener_equipo(equipo_id: int, db: Session = Depends(get_db)):
    equipo = db.get(Equipment, equipo_id)
    if equipo is None:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return equipo


@app.post(
    "/equipos/{equipo_id}/lecturas",
    response_model=schemas.LecturaIngestResponse,
    status_code=201,
)
def ingerir_lectura(
    equipo_id: int, payload: schemas.LecturaCreate, db: Session = Depends(get_db)
):
    equipo = db.get(Equipment, equipo_id)
    if equipo is None:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    lectura, alerta = services.ingest_reading(db, equipo, payload.model_dump())
    return {
        "lectura": lectura,
        "anomaly_score": lectura.anomaly_score,
        "es_anomalia": lectura.es_anomalia,
        "alerta": alerta,
    }


@app.get("/equipos/{equipo_id}/salud", response_model=schemas.SaludOut)
def salud_equipo(equipo_id: int, db: Session = Depends(get_db)):
    equipo = db.get(Equipment, equipo_id)
    if equipo is None:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return services.equipment_health(db, equipo)


@app.get("/alertas", response_model=list[schemas.AlertaOut])
def listar_alertas(
    equipo_id: int | None = None,
    severidad: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Alert).order_by(Alert.creado_en.desc())
    if equipo_id is not None:
        query = query.filter(Alert.equipo_id == equipo_id)
    if severidad is not None:
        query = query.filter(Alert.severidad == severidad)
    return query.limit(limit).all()
