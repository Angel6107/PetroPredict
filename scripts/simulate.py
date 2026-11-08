"""Simulador de sensores para PetroPredict.

Genera lecturas realistas para 3 equipos (bomba centrífuga, compresor y motor)
durante N horas, con degradación gradual y un evento de falla en el compresor.
Si la API está corriendo, envía las lecturas por HTTP; si no, escribe un CSV.

Todos los datos son SIMULADOS. No se usan datos reales de Pemex ni de ninguna
planta.
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

import httpx

EQUIPOS = [
    {
        "nombre": "Bomba centrífuga P-101",
        "tipo": "bomba_centrifuga",
        "ubicacion": "Estación de bombeo 1",
        "vibracion_nominal": 2.5,
        "temperatura_nominal": 62.0,
        "presion_nominal": 6.5,
    },
    {
        "nombre": "Compresor C-201",
        "tipo": "compresor",
        "ubicacion": "Planta de compresión",
        "vibracion_nominal": 3.2,
        "temperatura_nominal": 78.0,
        "presion_nominal": 12.0,
    },
    {
        "nombre": "Motor M-301",
        "tipo": "motor",
        "ubicacion": "Taller de motores",
        "vibracion_nominal": 1.8,
        "temperatura_nominal": 55.0,
        "presion_nominal": 2.0,
    },
]

# Hora en la que ocurre el evento de falla del compresor.
HORA_FALLA = 60


def generar_lecturas(equipo: dict, horas: int, seed: int = 7) -> list[dict]:
    """Genera una lectura por hora para un equipo."""
    rng = random.Random(f"{seed}-{equipo['nombre']}")
    lecturas = []
    for hora in range(horas):
        # Ruido proporcional al nominal: un motor de 2 bar no tiene el
        # mismo ruido absoluto que un compresor de 12 bar.
        vib = rng.gauss(equipo["vibracion_nominal"], 0.12 * equipo["vibracion_nominal"])
        temp = rng.gauss(equipo["temperatura_nominal"], 0.03 * equipo["temperatura_nominal"])
        pres = rng.gauss(equipo["presion_nominal"], 0.05 * equipo["presion_nominal"])
        if equipo["tipo"] == "bomba_centrifuga":
            # Desgaste leve y constante.
            vib += 0.005 * hora
            temp += 0.02 * hora
        elif equipo["tipo"] == "compresor":
            # Degradación gradual a partir de la hora 24.
            if hora >= 24:
                vib += 0.04 * (hora - 24)
                temp += 0.15 * (hora - 24)
            if hora == HORA_FALLA:
                # Evento de falla: vibración y temperatura se disparan.
                vib = 12.5
                temp = 98.0
                pres = equipo["presion_nominal"] * 0.7
        lecturas.append(
            {
                "equipo": equipo["nombre"],
                "hora": hora,
                "vibracion_rms": round(max(0.1, vib), 2),
                "temperatura": round(temp, 1),
                "presion": round(max(0.1, pres), 2),
                "horas_operacion": 1000.0 + hora,
            }
        )
    return lecturas


def escribir_csv(lecturas_por_equipo: dict[str, list[dict]], ruta: Path) -> int:
    """Escribe todas las lecturas en un CSV. Devuelve el número de filas."""
    total = 0
    with ruta.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "equipo",
                "hora",
                "vibracion_rms",
                "temperatura",
                "presion",
                "horas_operacion",
            ],
        )
        writer.writeheader()
        for lecturas in lecturas_por_equipo.values():
            writer.writerows(lecturas)
            total += len(lecturas)
    return total


def enviar_a_api(
    api_url: str, lecturas_por_equipo: dict[str, list[dict]]
) -> dict[str, int]:
    """Crea los equipos en la API y envía las lecturas. Devuelve contadores."""
    resumen = {"enviadas": 0, "anomalias": 0, "alertas": 0}
    # trust_env=False: ignora las variables de proxy del entorno, que
    # rompen httpx en algunas máquinas; la API es local.
    with httpx.Client(base_url=api_url, timeout=10.0, trust_env=False) as client:
        client.get("/health").raise_for_status()
        existentes = {e["nombre"]: e["id"] for e in client.get("/equipos").json()}
        for equipo in EQUIPOS:
            equipo_id = existentes.get(equipo["nombre"])
            if equipo_id is None:
                resp = client.post("/equipos", json=equipo)
                resp.raise_for_status()
                equipo_id = resp.json()["id"]
            for lectura in lecturas_por_equipo[equipo["nombre"]]:
                payload = {
                    "vibracion_rms": lectura["vibracion_rms"],
                    "temperatura": lectura["temperatura"],
                    "presion": lectura["presion"],
                    "horas_operacion": lectura["horas_operacion"],
                }
                resp = client.post(f"/equipos/{equipo_id}/lecturas", json=payload)
                resp.raise_for_status()
                body = resp.json()
                resumen["enviadas"] += 1
                if body["es_anomalia"]:
                    resumen["anomalias"] += 1
                if body["alerta"] is not None:
                    resumen["alertas"] += 1
    return resumen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Simulador de sensores de PetroPredict")
    parser.add_argument("--hours", type=int, default=72, help="Horas a simular")
    parser.add_argument("--api-url", default="http://localhost:8000", help="URL base de la API")
    parser.add_argument("--csv", type=Path, default=None, help="Escribir CSV en esta ruta")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)

    lecturas = {e["nombre"]: generar_lecturas(e, args.hours, args.seed) for e in EQUIPOS}
    total = sum(len(v) for v in lecturas.values())
    print(f"Generadas {total} lecturas simuladas ({args.hours} h x {len(EQUIPOS)} equipos)")

    if args.csv is not None:
        n = escribir_csv(lecturas, args.csv)
        print(f"CSV escrito en {args.csv} ({n} filas)")
        return 0

    try:
        resumen = enviar_a_api(args.api_url, lecturas)
    except (httpx.HTTPError, httpx.HTTPStatusError) as exc:
        ruta = Path("lecturas_simuladas.csv")
        n = escribir_csv(lecturas, ruta)
        print(f"API no disponible ({exc}); CSV escrito en {ruta} ({n} filas)")
        return 0
    print(
        f"Enviadas a la API: {resumen['enviadas']} lecturas, "
        f"{resumen['anomalias']} anómalas, {resumen['alertas']} alertas generadas"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
