"""Detección de anomalías, puntuación de salud y estimación de vida útil restante (RUL).

El modelo es un IsolationForest entrenado con datos de operación normal
SIMULADOS. Este proyecto no usa datos reales de Pemex ni de ninguna planta:
todos los datos de sensores son sintéticos y están etiquetados como tales.
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

FEATURES = ("vibracion_ratio", "temperatura_ratio", "presion_ratio", "tendencia_vibracion")

# Nivel de alarma de vibración en mm/s RMS (inspirado en ISO 10816).
VIBRATION_LIMIT = 7.1

# Valores nominales genéricos usados solo para generar los datos de
# entrenamiento. En producción cada lectura se normaliza con los valores
# nominales de SU propio equipo, así una bomba y un motor no se comparan
# con la misma referencia.
NOMINAL_GENERICO = {"vibracion": 2.8, "temperatura": 68.0, "presion": 8.0}


def generate_normal_data(n: int = 600, seed: int = 42) -> np.ndarray:
    """Genera datos simulados de operación normal para entrenar el detector.

    Las variables son RATIOS respecto al valor nominal del equipo
    (1.0 = operación nominal), por eso el mismo modelo sirve para bombas,
    compresores y motores con nominales distintos.
    """
    rng = np.random.default_rng(seed)
    vibracion = np.clip(rng.normal(1.0, 0.2, n), 0.2, 1.8)
    temperatura = np.clip(rng.normal(1.0, 0.07, n), 0.5, 1.25)
    presion = np.clip(rng.normal(1.0, 0.08, n), 0.1, 1.9)
    tendencia = np.clip(rng.normal(0.0, 0.05, n), -0.3, 0.3)
    return np.column_stack([vibracion, temperatura, presion, tendencia])


class AnomalyDetector:
    """IsolationForest sobre variables escaladas.

    La puntuación de anomalía va de 0 (normal) a 1 (muy anómalo) y se obtiene
    de la función de decisión del modelo: valores positivos indican
    normalidad y negativos anomalía.
    """

    def __init__(self, contamination: float = 0.05, random_state: int = 42):
        self.scaler = StandardScaler()
        self.model = IsolationForest(
            contamination=contamination,
            random_state=random_state,
            n_estimators=200,
        )
        self._fitted = False

    def fit(self, data: np.ndarray | None = None) -> "AnomalyDetector":
        if data is None:
            data = generate_normal_data()
        scaled = self.scaler.fit_transform(data)
        self.model.fit(scaled)
        # Rango de la función de decisión sobre los datos de entrenamiento:
        # se usa para reescalar la puntuación a 0-1 de forma lineal.
        decisiones = self.model.decision_function(scaled)
        self._dec_min = float(decisiones.min())
        self._dec_max = float(decisiones.max())
        self._fitted = True
        return self

    def anomaly_score(
        self,
        vibracion: float,
        temperatura: float,
        presion: float,
        tendencia: float = 0.0,
        vibracion_nominal: float = 2.8,
        temperatura_nominal: float = 68.0,
        presion_nominal: float = 8.0,
    ) -> float:
        """Puntuación de anomalía de 0 (normal) a 1 (muy anómalo).

        Las lecturas se normalizan como ratio respecto a los valores
        nominales del equipo, así el modelo no marca como anómalo a un
        motor sano solo porque sus valores absolutos difieren de los de
        una bomba.
        """
        if not self._fitted:
            self.fit()
        ratios = [
            vibracion / vibracion_nominal,
            temperatura / temperatura_nominal,
            presion / presion_nominal,
            tendencia,
        ]
        features = self.scaler.transform([ratios])
        decision = float(self.model.decision_function(features)[0])
        # Reescalado lineal: el mínimo de entrenamiento es anomalía 1 y
        # el máximo es anomalía 0. Un punto claramente fuera de lo normal
        # queda por encima del umbral de 0.6.
        if self._dec_max > self._dec_min:
            score = 1.0 - (decision - self._dec_min) / (self._dec_max - self._dec_min)
        else:
            score = 1.0 / (1.0 + np.exp(5.0 * decision))
        return round(float(np.clip(score, 0.0, 1.0)), 4)

    @staticmethod
    def is_anomaly(score: float, threshold: float = 0.6) -> bool:
        return score >= threshold


_detector: AnomalyDetector | None = None


def get_detector() -> AnomalyDetector:
    """Singleton del detector, entrenado una sola vez por proceso."""
    global _detector
    if _detector is None:
        _detector = AnomalyDetector().fit()
    return _detector


def health_score(
    vibracion: float,
    temperatura: float,
    presion: float,
    presion_nominal: float,
    anomaly_score: float,
    tendencia: float,
) -> float:
    """Puntuación de salud de 0 a 100. 100 es un equipo sano."""
    score = 100.0
    if vibracion > 4.5:
        score -= min(40.0, (vibracion - 4.5) * 8.0)
    if temperatura > 80.0:
        score -= min(25.0, (temperatura - 80.0) * 1.5)
    if presion_nominal > 0:
        desviacion = abs(presion - presion_nominal) / presion_nominal
        if desviacion > 0.2:
            score -= min(15.0, (desviacion - 0.2) * 50.0)
    score -= anomaly_score * 25.0
    if tendencia > 0.05:
        score -= min(20.0, tendencia * 100.0)
    return round(float(max(0.0, min(100.0, score))), 1)


def estimate_rul(
    horas: list[float],
    vibraciones: list[float],
    limite: float = VIBRATION_LIMIT,
) -> dict:
    """Estima la vida útil restante (RUL) por la tendencia de degradación.

    Ajusta una recta a vibración vs. horas de operación y extrapola hasta
    el límite de alarma. Si la vibración no crece, no hay degradación
    medible y el RUL es indefinido (None).
    """
    if len(horas) < 3:
        return {"rul_horas": None, "riesgo": "bajo", "tendencia": 0.0}
    pendiente = float(
        np.polyfit(
            np.asarray(horas, dtype=float),
            np.asarray(vibraciones, dtype=float),
            1,
        )[0]
    )
    actual = float(vibraciones[-1])
    if actual >= limite:
        return {"rul_horas": 0.0, "riesgo": "critico", "tendencia": round(pendiente, 4)}
    if pendiente <= 0.005:
        return {"rul_horas": None, "riesgo": "bajo", "tendencia": round(pendiente, 4)}
    rul = (limite - actual) / pendiente
    if rul < 24:
        riesgo = "critico"
    elif rul < 168:
        riesgo = "alto"
    elif rul < 720:
        riesgo = "medio"
    else:
        riesgo = "bajo"
    return {"rul_horas": round(float(rul), 1), "riesgo": riesgo, "tendencia": round(pendiente, 4)}
