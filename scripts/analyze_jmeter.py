#!/usr/bin/env python3
"""Calcula métricas desde un JTL CSV y genera la gráfica para el PPTX."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def as_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def percentile(values: list[int], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile_value
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def read_jtl(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        required = {"timeStamp", "elapsed", "success"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"El JTL no contiene las columnas obligatorias: {sorted(missing)}")
        return list(reader)


def duration_text(total_seconds: float) -> str:
    seconds = max(0, round(total_seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if hours:
        parts.append(f"{hours} h")
    if minutes:
        parts.append(f"{minutes} min")
    if seconds or not parts:
        parts.append(f"{seconds} s")
    return " ".join(parts)


def analyze(rows: list[dict[str, str]], timezone_name: str) -> tuple[dict, dict]:
    if not rows:
        raise ValueError("El JTL no contiene muestras")

    timestamps = [int(row["timeStamp"]) for row in rows]
    elapsed_values = [int(float(row["elapsed"])) for row in rows]
    end_timestamps = [timestamp + elapsed for timestamp, elapsed in zip(timestamps, elapsed_values)]
    start_ms = min(timestamps)
    end_ms = max(end_timestamps)
    duration_seconds = max((end_ms - start_ms) / 1000.0, 0.001)

    successes = sum(as_bool(row["success"]) for row in rows)
    failures = len(rows) - successes
    samples_by_second: Counter[int] = Counter()
    active_by_second: dict[int, int] = defaultdict(int)
    response_codes: Counter[str] = Counter()

    for row in rows:
        second = max(0, (int(row["timeStamp"]) - start_ms) // 1000)
        samples_by_second[second] += 1
        threads = row.get("allThreads") or row.get("grpThreads") or "0"
        try:
            active_by_second[second] = max(active_by_second[second], int(float(threads)))
        except ValueError:
            pass
        response_codes[row.get("responseCode", "sin código")] += 1

    last_second = max(samples_by_second)
    seconds = list(range(last_second + 1))
    tps_series = [samples_by_second.get(second, 0) for second in seconds]
    active_series = [active_by_second.get(second, 0) for second in seconds]

    zone = ZoneInfo(timezone_name)
    start_datetime = datetime.fromtimestamp(start_ms / 1000, zone)
    end_datetime = datetime.fromtimestamp(end_ms / 1000, zone)
    total = len(rows)

    metrics = {
        "start_iso": start_datetime.isoformat(),
        "end_iso": end_datetime.isoformat(),
        "start_display": start_datetime.strftime("%d/%m/%Y %I:%M:%S %p").lower(),
        "end_display": end_datetime.strftime("%d/%m/%Y %I:%M:%S %p").lower(),
        "duration_seconds": round(duration_seconds, 3),
        "duration_display": duration_text(duration_seconds),
        "transactions_total": total,
        "transactions_successful": successes,
        "transactions_failed": failures,
        "success_rate_percent": round(successes * 100 / total, 2),
        "error_rate_percent": round(failures * 100 / total, 2),
        "tps_average": round(total / duration_seconds, 2),
        "tps_maximum": max(tps_series, default=0),
        "elapsed_average_ms": round(mean(elapsed_values), 2),
        "elapsed_p90_ms": round(percentile(elapsed_values, 0.90), 2),
        "elapsed_p95_ms": round(percentile(elapsed_values, 0.95), 2),
        "active_users_maximum": max(active_series, default=0),
        "response_codes": dict(response_codes.most_common()),
    }
    series = {"seconds": seconds, "active_users": active_series, "tps": tps_series}
    return metrics, series


def create_chart(series: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    figure, axis_users = plt.subplots(figsize=(12, 5.4), dpi=160)
    axis_tps = axis_users.twinx()

    users_line = axis_users.plot(
        series["seconds"], series["active_users"], color="#2563EB", linewidth=2.4,
        label="Usuarios activos"
    )[0]
    tps_line = axis_tps.plot(
        series["seconds"], series["tps"], color="#F97316", linewidth=2.0,
        label="TPS", alpha=0.9
    )[0]

    axis_users.set_xlabel("Tiempo transcurrido (s)")
    axis_users.set_ylabel("Usuarios activos", color="#2563EB")
    axis_tps.set_ylabel("Transacciones por segundo", color="#F97316")
    axis_users.set_ylim(bottom=0)
    axis_tps.set_ylim(bottom=0)
    axis_users.grid(axis="y", color="#D1D5DB", linewidth=0.7, alpha=0.8)
    axis_users.spines[["top", "right"]].set_visible(False)
    axis_tps.spines["top"].set_visible(False)
    axis_users.legend(handles=[users_line, tps_line], loc="upper left", frameon=False, ncol=2)
    figure.tight_layout()
    figure.savefig(output, transparent=False, facecolor="white", bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jtl", required=True, type=Path)
    parser.add_argument("--metrics", required=True, type=Path)
    parser.add_argument("--chart", required=True, type=Path)
    parser.add_argument("--timezone", default="America/Lima")
    args = parser.parse_args()

    rows = read_jtl(args.jtl)
    metrics, series = analyze(rows, args.timezone)
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    create_chart(series, args.chart)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

