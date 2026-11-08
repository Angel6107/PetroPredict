"""Pruebas del simulador de sensores."""

import csv

from simulate import EQUIPOS, escribir_csv, generar_lecturas


def test_generar_lecturas_cantidad_y_campos():
    for equipo in EQUIPOS:
        lecturas = generar_lecturas(equipo, 72)
        assert len(lecturas) == 72
        for lectura in lecturas:
            assert lectura["vibracion_rms"] > 0
            assert lectura["temperatura"] > 0
            assert lectura["presion"] > 0
            assert lectura["horas_operacion"] >= 1000.0


def test_compresor_se_degrada_con_el_tiempo():
    compresor = next(e for e in EQUIPOS if e["tipo"] == "compresor")
    lecturas = generar_lecturas(compresor, 72)
    vib_inicio = sum(lec["vibracion_rms"] for lec in lecturas[10:15]) / 5
    vib_fin = sum(lec["vibracion_rms"] for lec in lecturas[65:70]) / 5
    assert vib_fin > vib_inicio


def test_evento_de_falla_del_compresor():
    compresor = next(e for e in EQUIPOS if e["tipo"] == "compresor")
    lecturas = generar_lecturas(compresor, 72)
    max_vib = max(lec["vibracion_rms"] for lec in lecturas)
    assert max_vib > 11.0
    falla = next(lec for lec in lecturas if lec["vibracion_rms"] > 11.0)
    assert falla["hora"] == 60
    assert falla["temperatura"] > 90.0


def test_motor_se_mantiene_estable():
    motor = next(e for e in EQUIPOS if e["tipo"] == "motor")
    lecturas = generar_lecturas(motor, 72)
    vibraciones = [lec["vibracion_rms"] for lec in lecturas]
    assert max(vibraciones) < 4.0
    assert min(vibraciones) > 0.5


def test_escribir_csv(tmp_path):
    lecturas = {e["nombre"]: generar_lecturas(e, 10) for e in EQUIPOS}
    ruta = tmp_path / "lecturas.csv"
    n = escribir_csv(lecturas, ruta)
    assert n == 30
    with ruta.open(newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert len(filas) == 30
    assert filas[0]["equipo"] == "Bomba centrífuga P-101"
