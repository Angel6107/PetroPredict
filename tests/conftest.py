"""Fixtures de pytest: base de datos SQLite temporal y TestClient."""

import os
import sys
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp())
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp / 'test.db'}"

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from petropredict.database import engine, init_db  # noqa: E402
from petropredict.main import app  # noqa: E402
from petropredict.models import Base  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _db():
    init_db()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def equipo(client):
    resp = client.post(
        "/equipos",
        json={
            "nombre": "Bomba P-101",
            "tipo": "bomba_centrifuga",
            "ubicacion": "Planta 1",
            "vibracion_nominal": 2.5,
            "temperatura_nominal": 62.0,
            "presion_nominal": 6.5,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def lectura_normal(horas: float = 1000.0) -> dict:
    return {
        "vibracion_rms": 2.6,
        "temperatura": 64.0,
        "presion": 6.4,
        "horas_operacion": horas,
    }


def lectura_degradada(horas: float = 1000.0) -> dict:
    return {
        "vibracion_rms": 9.5,
        "temperatura": 96.0,
        "presion": 6.0,
        "horas_operacion": horas,
    }
