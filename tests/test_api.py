"""Pruebas de los endpoints de la API."""

from conftest import lectura_degradada, lectura_normal


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_crear_equipo(client):
    resp = client.post(
        "/equipos",
        json={"nombre": "Compresor C-201", "tipo": "compresor", "ubicacion": "Planta 2"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["nombre"] == "Compresor C-201"
    assert body["tipo"] == "compresor"
    assert body["id"] > 0


def test_crear_equipo_tipo_invalido(client):
    resp = client.post("/equipos", json={"nombre": "X", "tipo": "turbina"})
    assert resp.status_code == 422


def test_listar_equipos(client, equipo):
    resp = client.get("/equipos")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["nombre"] == "Bomba P-101"


def test_obtener_equipo_inexistente(client):
    resp = client.get("/equipos/9999")
    assert resp.status_code == 404


def test_ingerir_lectura_normal(client, equipo):
    resp = client.post(f"/equipos/{equipo['id']}/lecturas", json=lectura_normal())
    assert resp.status_code == 201
    body = resp.json()
    assert body["anomaly_score"] < 0.6
    assert body["es_anomalia"] is False
    assert body["alerta"] is None
    assert body["lectura"]["vibracion_rms"] == 2.6


def test_ingerir_lectura_degradada_genera_alerta(client, equipo):
    resp = client.post(f"/equipos/{equipo['id']}/lecturas", json=lectura_degradada())
    assert resp.status_code == 201
    body = resp.json()
    assert body["anomaly_score"] > 0.6
    assert body["es_anomalia"] is True
    assert body["alerta"] is not None
    assert body["alerta"]["severidad"] == "critica"
    assert body["alerta"]["equipo_id"] == equipo["id"]


def test_ingerir_lectura_equipo_inexistente(client):
    resp = client.post("/equipos/9999/lecturas", json=lectura_normal())
    assert resp.status_code == 404


def test_ingerir_lectura_invalida(client, equipo):
    resp = client.post(
        f"/equipos/{equipo['id']}/lecturas",
        json={"vibracion_rms": -1.0, "temperatura": 60.0, "presion": 6.0, "horas_operacion": 1.0},
    )
    assert resp.status_code == 422


def test_salud_equipo_saludable(client, equipo):
    for i in range(5):
        client.post(f"/equipos/{equipo['id']}/lecturas", json=lectura_normal(1000.0 + i))
    resp = client.get(f"/equipos/{equipo['id']}/salud")
    assert resp.status_code == 200
    body = resp.json()
    assert body["salud"] > 80
    assert body["estado"] == "saludable"
    assert body["alertas_activas"] == 0
    assert body["ultima_lectura"] is not None


def test_salud_equipo_sin_lecturas(client, equipo):
    resp = client.get(f"/equipos/{equipo['id']}/salud")
    assert resp.status_code == 200
    body = resp.json()
    assert body["salud"] == 100.0
    assert body["estado"] == "sin_datos"
    assert body["rul_horas"] is None


def test_salud_equipo_inexistente(client):
    resp = client.get("/equipos/9999/salud")
    assert resp.status_code == 404


def test_listar_alertas(client, equipo):
    client.post(f"/equipos/{equipo['id']}/lecturas", json=lectura_degradada())
    client.post(f"/equipos/{equipo['id']}/lecturas", json=lectura_normal(1001.0))
    resp = client.get("/alertas")
    assert resp.status_code == 200
    alertas = resp.json()
    assert len(alertas) == 1
    assert alertas[0]["severidad"] == "critica"

    resp = client.get("/alertas", params={"equipo_id": equipo["id"], "severidad": "media"})
    assert resp.json() == []

    resp = client.get("/alertas", params={"severidad": "critica"})
    assert len(resp.json()) == 1
