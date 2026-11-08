"""Configuración de PetroPredict leída de variables de entorno."""

import os

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./petropredict.db")

# Puntuación de anomalía (0-1) a partir de la cual se genera una alerta.
ANOMALY_THRESHOLD = float(os.environ.get("ANOMALY_THRESHOLD", "0.6"))

# Nivel de alarma de vibración en mm/s RMS (inspirado en ISO 10816).
VIBRATION_LIMIT = float(os.environ.get("VIBRATION_LIMIT", "7.1"))

# Temperatura de alarma en °C.
TEMPERATURE_LIMIT = float(os.environ.get("TEMPERATURE_LIMIT", "85.0"))
