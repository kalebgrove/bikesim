import io
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from schemas import TelemetryPoint


def _fig_to_png(fig: plt.Figure, dpi: int = 110) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def _speed_power_chart(points: list[TelemetryPoint]) -> bytes:
    ts = [p.t for p in points]
    speed_kph = [p.speed * 3.6 for p in points]
    power = [p.realizedPower for p in points]

    fig, ax1 = plt.subplots(figsize=(10, 4))
    ax1.set_xlabel("Time (min)")
    ax1.set_ylabel("Speed (km/h)", color="#1f77b4")
    ax1.plot([t / 60 for t in ts], speed_kph, color="#1f77b4", linewidth=1)
    ax1.tick_params(axis="y", labelcolor="#1f77b4")
    ax1.grid(True, alpha=0.3)

    ax2 = ax1.twinx()
    ax2.set_ylabel("Realized Power (W)", color="#d62728")
    ax2.fill_between([t / 60 for t in ts], power, alpha=0.15, color="#d62728")
    ax2.plot([t / 60 for t in ts], power, color="#d62728", linewidth=0.8, alpha=0.8)
    ax2.tick_params(axis="y", labelcolor="#d62728")

    plt.title("Speed & Power")
    return _fig_to_png(fig)


def _elevation_grade_chart(points: list[TelemetryPoint]) -> bytes:
    dist_km = [p.dist for p in points]
    elevation = [p.elevation for p in points]
    grade = [max(min(p.grade, 30), -30) for p in points]  # clip for display

    fig, ax1 = plt.subplots(figsize=(10, 4))
    ax1.fill_between(dist_km, elevation, alpha=0.25, color="#2ca02c")
    ax1.plot(dist_km, elevation, color="#2ca02c", linewidth=1.5)
    ax1.set_xlabel("Distance (km)")
    ax1.set_ylabel("Elevation (m)", color="#2ca02c")
    ax1.tick_params(axis="y", labelcolor="#2ca02c")
    ax1.grid(True, alpha=0.3)

    ax2 = ax1.twinx()
    ax2.set_ylabel("Grade (%)", color="#ff7f0e")
    ax2.plot(dist_km, grade, color="#ff7f0e", linewidth=0.6, alpha=0.7)
    ax2.tick_params(axis="y", labelcolor="#ff7f0e")
    ax2.axhline(0, color="#ff7f0e", linewidth=0.5, alpha=0.4)

    plt.title("Elevation Profile & Grade")
    return _fig_to_png(fig)


def _energy_chart(points: list[TelemetryPoint]) -> bytes:
    dist_km = [p.dist for p in points]
    energy_kj = [p.totalEnergy for p in points]

    fig, ax = plt.subplots(figsize=(10, 3))
    ax.fill_between(dist_km, energy_kj, alpha=0.3, color="#9467bd")
    ax.plot(dist_km, energy_kj, color="#9467bd", linewidth=1.5)
    ax.set_xlabel("Distance (km)")
    ax.set_ylabel("Cumulative Energy (kJ)")
    ax.set_title("Energy Expended")
    ax.grid(True, alpha=0.3)

    return _fig_to_png(fig)


def render_graphs(points: list[TelemetryPoint]) -> list[tuple[str, bytes]]:
    """Render charts from a completed simulation's history.

    Returns a list of (filename, png_bytes) tuples.
    Failures in any individual chart are caught and skipped.
    """
    if len(points) < 2:
        return []

    renderers = [
        ("speed_power.png", _speed_power_chart),
        ("elevation_grade.png", _elevation_grade_chart),
        ("energy.png", _energy_chart),
    ]

    charts: list[tuple[str, bytes]] = []
    for name, fn in renderers:
        try:
            charts.append((name, fn(points)))
        except Exception:
            continue
    return charts
