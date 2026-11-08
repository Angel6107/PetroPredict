# PetroPredict — Mantenimiento predictivo para equipos petroleros

Sistema de mantenimiento predictivo para bombas centrífugas, compresores y
motores de instalaciones petroleras. Los sensores reportan vibración
(mm/s RMS), temperatura (°C), presión (bar) y horas de operación. El sistema
detecta anomalías, calcula una puntuación de salud (0–100) y estima la vida
útil restante (RUL) de cada equipo.

> **Aviso sobre los datos:** todos los datos de sensores de este proyecto son
> **simulados**. No se usan datos reales de Pemex ni de ninguna planta o
> empresa. El simulador incluido genera lecturas sintéticas con degradación
> gradual y un evento de falla para demostrar el sistema.

## Arquitectura

```text
src/petropredict/
├── main.py       API REST (FastAPI): equipos, lecturas, salud, alertas
├── models.py     Dominio: Equipment, SensorReading, Alert (SQLAlchemy)
├── schemas.py    Contratos de la API (Pydantic v2)
├── services.py   Ingesta de lecturas, tendencia y salud del equipo
├── ml.py         IsolationForest, puntuación de salud y estimación de RUL
├── database.py   SQLite por defecto, PostgreSQL con DATABASE_URL
└── config.py     Variables de entorno

scripts/simulate.py   Simulador de sensores (3 equipos, N horas)
tests/                pytest: API, ML, servicios y simulador
```

## Cómo funciona el modelo

1. **Detección de anomalías:** un `IsolationForest` de scikit-learn, entrenado
   con 600 muestras simuladas de operación normal. Cada lectura se
   normaliza como ratio respecto a los valores nominales de SU equipo
   (vibración, temperatura y presión divididas entre su nominal), así el
   mismo modelo sirve para bombas, compresores y motores sin marcar como
   anómalo a un equipo sano solo por tener nominales distintos. Las
   variables se escalan con `StandardScaler`. Cada lectura nueva recibe
   una puntuación de anomalía de 0 (normal) a 1 (muy anómala); a partir
   de 0.6 se marca como anomalía.
2. **Puntuación de salud (0–100):** empieza en 100 y descuenta puntos por
   vibración alta, temperatura alta, desviación de presión, anomalía y
   tendencia de vibración creciente.
3. **RUL (vida útil restante):** ajusta una recta a vibración vs. horas de
   operación y extrapola hasta el límite de alarma de 7.1 mm/s RMS
   (inspirado en ISO 10816). Si la vibración no crece, el RUL es indefinido.
4. **Alertas:** se generan automáticamente al ingerir una lectura, con
   severidad `media`, `alta` o `critica` según la anomalía y los límites
   superados.

## Uso local

```bash
python -m venv .venv
source .venv/bin/activate        # En Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn petropredict.main:app --reload   # con PYTHONPATH=src
```

La API queda en http://localhost:8000 y la documentación interactiva en
http://localhost:8000/docs. La base SQLite se crea sola como
`petropredict.db`.

## Uso con Docker

```bash
docker compose up --build
```

Levanta la API en el puerto 8000 y PostgreSQL 16 en el 5432. Para usar solo
la API con SQLite:

```bash
docker build -t petropredict .
docker run -p 8000:8000 petropredict
```

## Simulador de sensores

Genera lecturas para una bomba centrífuga, un compresor y un motor durante
N horas, con degradación gradual y un evento de falla en el compresor
(hora 60). Si la API está corriendo, envía las lecturas; si no, escribe un CSV.

```bash
# En otra terminal, con la API corriendo:
python scripts/simulate.py --hours 72
# Solo CSV:
python scripts/simulate.py --hours 72 --csv lecturas.csv
```

## API

| Método | Ruta | Descripción |
| ------ | ---- | ----------- |
| GET | `/health` | Estado de la API |
| POST | `/equipos` | Registrar un equipo |
| GET | `/equipos` | Listar equipos |
| GET | `/equipos/{id}` | Detalle de un equipo |
| POST | `/equipos/{id}/lecturas` | Ingerir una lectura (devuelve anomalía y alerta) |
| GET | `/equipos/{id}/salud` | Salud, RUL y riesgo del equipo |
| GET | `/alertas` | Listar alertas (`?equipo_id=&severidad=&limit=`) |

Ejemplo de ingesta:

```bash
curl -X POST http://localhost:8000/equipos/1/lecturas \
  -H "Content-Type: application/json" \
  -d '{"vibracion_rms": 2.6, "temperatura": 64.0, "presion": 6.5, "horas_operacion": 1000}'
```

## Pruebas y calidad

```bash
pip install -r requirements-dev.txt
ruff check src tests scripts
pytest --cov=petropredict --cov-report=term-missing --cov-fail-under=80
```

La cobertura mínima exigida es 80%. El CI de GitHub Actions corre Ruff,
pytest y la construcción de la imagen Docker en cada push a `main`.

## Variables de entorno

| Variable | Por defecto | Descripción |
| -------- | ----------- | ----------- |
| `DATABASE_URL` | `sqlite:///./petropredict.db` | URL de la base de datos |
| `ANOMALY_THRESHOLD` | `0.6` | Umbral de anomalía para alertas |
| `VIBRATION_LIMIT` | `7.1` | Límite de alarma de vibración (mm/s) |
| `TEMPERATURE_LIMIT` | `85.0` | Límite de alarma de temperatura (°C) |

## Roadmap

- [ ] Dashboard web con gráficas de vibración, temperatura y salud por equipo.
- [ ] Conjunto de datos real y público (por ejemplo, NASA C-MAPSS) para
      entrenar el modelo con datos de degradación reales.
- [ ] TimescaleDB para series de tiempo y retención de lecturas.
- [ ] Modelo de RUL con regresión supervisada en lugar de extrapolación lineal.
- [ ] Notificaciones (correo o webhook) cuando se genera una alerta crítica.
- [ ] Autenticación por roles y despliegue en Render con PostgreSQL.
- [ ] Pruebas de carga del endpoint de ingesta.
