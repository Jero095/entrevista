"""
Generador de un dataset sintético de alarmas industriales (SCADA) en CSV.

Simula la exportación del "alarm journal" de un SCADA legacy: cada fila es un
EVENTO del ciclo de vida de una alarma (ACTIVE -> ACK -> RTN), siguiendo las
convenciones de ISA-18.2 / IEC 62682.

Inyecta intencionalmente problemas de calidad de datos típicos de entornos
industriales (ver INJECTED_ISSUES y docs/dataset.md) para que el proceso de
ingesta tenga que resolverlos.

Uso:
    python data_generation/generate_dataset.py --alarms 8000 --seed 42
"""

from __future__ import annotations

import argparse
import csv
import random
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

CSV_COLUMNS = [
    "id_evento",
    "timestamp",
    "tag",
    "descripcion",
    "area",
    "tipo_alarma",
    "criticidad",
    "estado",
    "valor",
    "limite",
    "unidad",
]

# Probabilidad de que un evento reciba cada tipo de defecto.
DEFECT_RATE = {
    "timestamp_format": 0.35,  # formato de fecha alternativo (parseable)
    "timestamp_invalid": 0.01,  # fecha imposible / basura
    "timestamp_null": 0.01,
    "tag_dirty": 0.10,  # minúsculas, espacios, '_' en vez de '-'
    "tag_null": 0.005,
    "priority_variant": 0.25,  # sinónimos: "Alta", "3", "P1", "crit"...
    "priority_null": 0.03,
    "state_variant": 0.20,  # "Acknowledged", "ACKED", "Cleared"...
    "value_variant": 0.08,  # coma decimal, notación científica
    "value_bad_quality": 0.03,  # "Bad Quality", "#####", "NaN"
    "value_null": 0.03,
    "area_null": 0.05,
    "duplicate": 0.02,  # el SCADA reenvía el mismo evento
}

PRIORITY_VARIANTS = {
    "CRITICAL": ["critical", "Critical", "CRIT", "Crítica", "P1", "1", "Urgent"],
    "HIGH": ["high", "High", "HI", "Alta", "P2", "2"],
    "MEDIUM": ["medium", "Medium", "MED", "Media", "P3", "3"],
    "LOW": ["low", "Low", "LO", "Baja", "P4", "4"],
}

STATE_VARIANTS = {
    "ACTIVE": ["Active", "active", "ACT", "ALM", "UNACK_ALM"],
    "ACK": ["Acknowledged", "ACKED", "ack", "ACK_ALM"],
    "RTN": ["Return", "RTN_UNACK", "Cleared", "NORMAL", "OK"],
}

UNPARSEABLE_TIMESTAMPS = ["N/A", "0000-00-00 00:00:00", "31/02/2026 10:00:00", "##########", "ERR"]
BAD_QUALITY_VALUES = ["Bad Quality", "#####", "NaN", "COMM FAIL", "---"]


@dataclass(frozen=True)
class TagSpec:
    tag: str
    description: str
    area: str
    unit: str
    normal: float  # valor de operación normal
    alarm_type: str
    limit: float
    priority: str
    weight: float  # frecuencia relativa de alarmas (bad actors >> resto)


# Catálogo de instrumentos. Unos pocos "bad actors" concentran la mayoría de los
# eventos, como ocurre en planta real (y hace interesante el endpoint de top tags).
TAGS: list[TagSpec] = [
    TagSpec("PT-101", "Presión descarga bomba P-101", "Bombeo", "bar", 6.0, "HI", 8.5, "HIGH", 18),
    TagSpec("PT-102", "Presión succión bomba P-102", "Bombeo", "bar", 1.5, "LO", 0.5, "MEDIUM", 3),
    TagSpec("FT-201", "Flujo entrada tanque TK-200", "Tanques", "m3/h", 120.0, "LO", 80.0, "MEDIUM", 12),
    TagSpec("LT-202", "Nivel tanque TK-200", "Tanques", "%", 55.0, "HIHI", 95.0, "CRITICAL", 4),
    TagSpec("LT-203", "Nivel tanque TK-201", "Tanques", "%", 50.0, "LOLO", 5.0, "CRITICAL", 2),
    TagSpec("TT-301", "Temperatura reactor R-300", "Reactor", "°C", 180.0, "HI", 210.0, "HIGH", 6),
    TagSpec("TT-302", "Temperatura chaqueta R-300", "Reactor", "°C", 90.0, "HIHI", 130.0, "CRITICAL", 2),
    TagSpec("PT-303", "Presión reactor R-300", "Reactor", "bar", 12.0, "HIHI", 18.0, "CRITICAL", 1.5),
    TagSpec("AT-304", "pH salida reactor", "Reactor", "pH", 7.0, "DEV", 1.0, "MEDIUM", 5),
    TagSpec("VT-401", "Vibración compresor C-400", "Compresión", "mm/s", 3.0, "HI", 7.1, "HIGH", 9),
    TagSpec("TT-402", "Temperatura aceite C-400", "Compresión", "°C", 60.0, "HI", 85.0, "MEDIUM", 3),
    TagSpec("ZS-403", "Estado válvula XV-403", "Compresión", "", 1.0, "DISC", 0.0, "LOW", 7),
    TagSpec("FT-501", "Flujo vapor caldera B-500", "Servicios", "t/h", 25.0, "ROC", 5.0, "LOW", 4),
    TagSpec("PT-502", "Presión aire instrumentos", "Servicios", "bar", 7.0, "LO", 5.5, "HIGH", 2),
    TagSpec("ET-503", "Corriente motor M-503", "Servicios", "A", 45.0, "HI", 60.0, "LOW", 2.5),
]


def alarm_value(spec: TagSpec, rng: random.Random) -> float:
    """Valor del proceso en el instante en que se activa la alarma (cruza el límite)."""
    overshoot = abs(spec.limit - spec.normal) * rng.uniform(0.01, 0.15)
    if spec.alarm_type in ("HI", "HIHI"):
        return spec.limit + overshoot
    if spec.alarm_type in ("LO", "LOLO"):
        return max(spec.limit - overshoot, 0.0)
    if spec.alarm_type == "DEV":
        return spec.normal + rng.choice([-1, 1]) * (spec.limit + rng.uniform(0.05, 0.5))
    if spec.alarm_type == "ROC":
        return spec.limit + rng.uniform(0.5, 4.0)
    return 0.0  # DISC: el estado discreto cae a 0


def return_value(spec: TagSpec, rng: random.Random) -> float:
    """Valor del proceso cuando la condición vuelve a normal."""
    if spec.alarm_type == "DISC":
        return 1.0
    return spec.normal + rng.gauss(0, abs(spec.limit - spec.normal) * 0.1)


def build_clean_events(n_alarms: int, start: datetime, end: datetime, rng: random.Random) -> list[dict]:
    """Genera eventos limpios (en UTC) siguiendo el ciclo de vida ACTIVE -> ACK -> RTN."""
    events: list[dict] = []
    weights = [t.weight for t in TAGS]
    span_seconds = (end - start).total_seconds()

    for _ in range(n_alarms):
        spec = rng.choices(TAGS, weights=weights, k=1)[0]
        t_active = start + timedelta(seconds=rng.uniform(0, span_seconds))
        base = {
            "tag": spec.tag,
            "description": spec.description,
            "area": spec.area,
            "alarm_type": spec.alarm_type,
            "priority": spec.priority,
            "limit": spec.limit,
            "unit": spec.unit,
        }

        events.append({**base, "timestamp": t_active, "state": "ACTIVE",
                       "value": alarm_value(spec, rng)})

        # Las críticas se reconocen rápido; las LOW a veces nunca (alarm flood real).
        ack_probability = {"CRITICAL": 0.98, "HIGH": 0.9, "MEDIUM": 0.75, "LOW": 0.5}[spec.priority]
        t_ack = None
        if rng.random() < ack_probability:
            t_ack = t_active + timedelta(seconds=rng.expovariate(1 / 120))
            events.append({**base, "timestamp": t_ack, "state": "ACK",
                           "value": alarm_value(spec, rng)})

        # Algunas alarmas siguen activas al final del periodo exportado (sin RTN).
        if rng.random() < 0.95:
            t_rtn = (t_ack or t_active) + timedelta(seconds=rng.expovariate(1 / 600))
            events.append({**base, "timestamp": t_rtn, "state": "RTN",
                           "value": return_value(spec, rng)})

    events.sort(key=lambda e: e["timestamp"])
    return events


def format_timestamp(ts: datetime, rng: random.Random) -> str:
    """Formatos heterogéneos: distintos SCADA/exportaciones/zonas horarias mezclados."""
    local = ts.astimezone(timezone(timedelta(hours=-5)))  # hora local de planta (UTC-5)
    formats = [
        lambda: ts.strftime("%Y-%m-%d %H:%M:%S"),                   # sin zona (se asume UTC)
        lambda: local.strftime("%d/%m/%Y %H:%M:%S"),                 # local, día primero
        lambda: local.strftime("%m-%d-%Y %I:%M:%S %p"),              # local, estilo US con AM/PM
        lambda: local.isoformat(timespec="milliseconds"),            # ISO con offset -05:00
        lambda: ts.strftime("%Y/%m/%d %H:%M:%S.%f")[:-3],            # milisegundos
        lambda: str(int(ts.timestamp())),                            # epoch en segundos
        lambda: str(int(ts.timestamp() * 1000)),                     # epoch en milisegundos
        lambda: ts.strftime("%Y%m%dT%H%M%SZ"),                       # ISO básico compacto
    ]
    return rng.choice(formats)()


def dirty_tag(tag: str, rng: random.Random) -> str:
    variants = [
        tag.lower(),
        f" {tag} ",
        tag.replace("-", "_"),
        tag.replace("-", ""),
        f"{tag}\t",
        tag.lower().replace("-", " "),
    ]
    return rng.choice(variants)


def format_value(value: float, rng: random.Random) -> str:
    if rng.random() < DEFECT_RATE["value_variant"]:
        return rng.choice([
            f"{value:.2f}".replace(".", ","),  # coma decimal (configuración regional)
            f"{value:.3e}",                    # notación científica
            f"{value:.6f}  ",                  # exceso de precisión y espacios
        ])
    return f"{value:.2f}"


def apply_defects(event: dict, event_id: int, rng: random.Random, issues: Counter) -> dict:
    """Convierte un evento limpio en una fila 'legacy' con problemas de calidad."""
    row = {
        "id_evento": str(event_id),
        "tag": event["tag"],
        "descripcion": event["description"],
        "area": event["area"],
        "tipo_alarma": event["alarm_type"],
        "criticidad": event["priority"],
        "estado": event["state"],
        "valor": format_value(event["value"], rng),
        "limite": f"{event['limit']:.2f}",
        "unidad": event["unit"],
    }

    roll = rng.random()
    if roll < DEFECT_RATE["timestamp_null"]:
        row["timestamp"] = ""
        issues["timestamp_null"] += 1
    elif roll < DEFECT_RATE["timestamp_null"] + DEFECT_RATE["timestamp_invalid"]:
        row["timestamp"] = rng.choice(UNPARSEABLE_TIMESTAMPS)
        issues["timestamp_invalid"] += 1
    elif rng.random() < DEFECT_RATE["timestamp_format"]:
        row["timestamp"] = format_timestamp(event["timestamp"], rng)
        issues["timestamp_format"] += 1
    else:
        row["timestamp"] = event["timestamp"].strftime("%Y-%m-%dT%H:%M:%SZ")

    if rng.random() < DEFECT_RATE["tag_null"]:
        row["tag"] = ""
        issues["tag_null"] += 1
    elif rng.random() < DEFECT_RATE["tag_dirty"]:
        row["tag"] = dirty_tag(row["tag"], rng)
        issues["tag_dirty"] += 1

    if rng.random() < DEFECT_RATE["priority_null"]:
        row["criticidad"] = ""
        issues["priority_null"] += 1
    elif rng.random() < DEFECT_RATE["priority_variant"]:
        row["criticidad"] = rng.choice(PRIORITY_VARIANTS[row["criticidad"]])
        issues["priority_variant"] += 1

    if rng.random() < DEFECT_RATE["state_variant"]:
        row["estado"] = rng.choice(STATE_VARIANTS[row["estado"]])
        issues["state_variant"] += 1

    roll = rng.random()
    if roll < DEFECT_RATE["value_null"]:
        row["valor"] = ""
        issues["value_null"] += 1
    elif roll < DEFECT_RATE["value_null"] + DEFECT_RATE["value_bad_quality"]:
        row["valor"] = rng.choice(BAD_QUALITY_VALUES)
        issues["value_bad_quality"] += 1

    if rng.random() < DEFECT_RATE["area_null"]:
        row["area"] = rng.choice(["", "NULL", "null", "-"])
        issues["area_null"] += 1

    return row


def generate(n_alarms: int, days: int, seed: int) -> tuple[list[dict], Counter]:
    rng = random.Random(seed)
    end = datetime(2026, 9, 30, tzinfo=timezone.utc)
    start = end - timedelta(days=days)

    clean_events = build_clean_events(n_alarms, start, end, rng)
    issues: Counter = Counter()
    rows: list[dict] = []

    for event_id, event in enumerate(clean_events, start=1):
        row = apply_defects(event, event_id, rng, issues)
        rows.append(row)
        if rng.random() < DEFECT_RATE["duplicate"]:
            rows.append(dict(row))  # duplicado exacto: mismo id_evento
            issues["duplicate"] += 1

    return rows, issues


def write_csv(rows: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig: los exports de herramientas Windows suelen incluir BOM.
    with output.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, delimiter=",", quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera un dataset sintético de alarmas SCADA con defectos.")
    parser.add_argument("--alarms", type=int, default=8000, help="Número de alarmas (cada una genera 1-3 eventos).")
    parser.add_argument("--days", type=int, default=90, help="Días de histórico a simular.")
    parser.add_argument("--seed", type=int, default=42, help="Semilla para reproducibilidad.")
    parser.add_argument("--output", type=Path, default=Path("data/raw/alarms.csv"))
    args = parser.parse_args()

    rows, issues = generate(args.alarms, args.days, args.seed)
    write_csv(rows, args.output)

    print(f"Generadas {len(rows)} filas ({args.alarms} alarmas) en {args.output}")
    print("Defectos inyectados:")
    for name, count in sorted(issues.items(), key=lambda kv: -kv[1]):
        print(f"  {name:<22} {count:>6}")


if __name__ == "__main__":
    main()
