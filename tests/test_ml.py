"""Pruebas unitarias del módulo de ML: detector, salud y RUL."""

from petropredict import ml


def test_detector_lectura_normal_puntaje_bajo():
    detector = ml.get_detector()
    score = detector.anomaly_score(2.6, 64.0, 6.5, tendencia=0.0)
    assert score < 0.6


def test_detector_motor_sano_no_es_anomalia():
    # Regresión: un motor sano (nominales bajos) no debe marcar anomalía
    # solo porque sus valores absolutos difieren de los de una bomba.
    detector = ml.get_detector()
    score = detector.anomaly_score(
        1.8,
        55.0,
        2.0,
        tendencia=0.0,
        vibracion_nominal=1.8,
        temperatura_nominal=55.0,
        presion_nominal=2.0,
    )
    assert score < 0.6


def test_detector_degradada_puntaje_alto():
    detector = ml.get_detector()
    score = detector.anomaly_score(10.0, 98.0, 13.0, tendencia=0.4)
    assert score > 0.6


def test_detector_es_anomalia_umbral():
    assert ml.AnomalyDetector.is_anomaly(0.59) is False
    assert ml.AnomalyDetector.is_anomaly(0.60) is True


def test_health_score_equipo_sano_cerca_de_100():
    score = ml.health_score(2.6, 64.0, 6.5, 6.5, 0.3, 0.0)
    assert score > 90


def test_health_score_equipo_degradado_bajo():
    score = ml.health_score(8.5, 95.0, 6.5, 6.5, 0.9, 0.3)
    assert score < 50


def test_health_score_nunca_fuera_de_rango():
    assert 0.0 <= ml.health_score(25.0, 150.0, 40.0, 6.5, 1.0, 2.0) <= 100.0


def test_rul_estable_es_indefinido():
    resultado = ml.estimate_rul([1000.0, 1001.0, 1002.0], [2.5, 2.6, 2.5])
    assert resultado["rul_horas"] is None
    assert resultado["riesgo"] == "bajo"


def test_rul_degradacion_da_valor_finito():
    horas = [1000.0 + i for i in range(10)]
    vibraciones = [3.0 + 0.2 * i for i in range(10)]
    resultado = ml.estimate_rul(horas, vibraciones)
    assert resultado["rul_horas"] is not None
    assert resultado["rul_horas"] > 0
    assert resultado["riesgo"] in ("bajo", "medio", "alto", "critico")


def test_rul_limite_alcanzado_es_cero_y_critico():
    resultado = ml.estimate_rul([1000.0, 1001.0, 1002.0], [6.5, 7.0, 7.5])
    assert resultado["rul_horas"] == 0.0
    assert resultado["riesgo"] == "critico"


def test_rul_sin_datos_suficientes():
    resultado = ml.estimate_rul([1000.0], [2.5])
    assert resultado["rul_horas"] is None
