"""Pruebas de servicios: tendencia de vibración y salud con degradación."""

from conftest import lectura_normal


def test_tendencia_crece_con_degradacion(client, equipo):
    for i in range(8):
        client.post(
            f"/equipos/{equipo['id']}/lecturas",
            json={
                "vibracion_rms": 2.5 + 0.4 * i,
                "temperatura": 64.0 + i,
                "presion": 6.5,
                "horas_operacion": 1000.0 + i,
            },
        )
    resp = client.get(f"/equipos/{equipo['id']}/salud")
    body = resp.json()
    assert body["tendencia_vibracion"] > 0.1
    assert body["rul_horas"] is not None
    assert body["estado"] in ("atencion", "critico")


def test_tendencia_cero_sin_lecturas(client, equipo):
    resp = client.get(f"/equipos/{equipo['id']}/salud")
    assert resp.json()["tendencia_vibracion"] == 0.0


def test_salud_empeora_con_lecturas_malas(client, equipo):
    for i in range(3):
        client.post(f"/equipos/{equipo['id']}/lecturas", json=lectura_normal(1000.0 + i))
    resp_sano = client.get(f"/equipos/{equipo['id']}/salud")
    for i in range(3):
        client.post(
            f"/equipos/{equipo['id']}/lecturas",
            json={
                "vibracion_rms": 6.0 + i,
                "temperatura": 90.0,
                "presion": 6.5,
                "horas_operacion": 1003.0 + i,
            },
        )
    resp_malo = client.get(f"/equipos/{equipo['id']}/salud")
    assert resp_malo.json()["salud"] < resp_sano.json()["salud"]
    assert resp_malo.json()["alertas_activas"] > 0
