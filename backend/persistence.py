import gzip
import json
import logging
from typing import Any

from db import supabase
from graphs import render_graphs
from schemas import TelemetryPoint

logger = logging.getLogger("bikesim.persistence")

BUCKET = "simulations"


def ensure_bucket() -> None:
    """Create the storage bucket if it does not already exist."""
    try:
        existing = supabase.storage.get_bucket(BUCKET)
        if existing is not None:
            return
    except Exception:
        pass
    try:
        supabase.storage.create_bucket(BUCKET, options={"public": False})
    except Exception:
        pass


def persist_session(
    sim_id: str,
    route_name: str,
    rider_ref: str | None,
    status: str,
    stop_reason: str | None,
    config: dict[str, Any],
    summary: dict[str, Any] | None,
    history: list[TelemetryPoint],
    created_at: str,
) -> None:
    """Save telemetry + charts to Storage and upsert a DB row."""
    try:
        ensure_bucket()

        # ── telemetry payload ──────────────────────────────────────
        payload = json.dumps([p.model_dump() for p in history]).encode()
        gz = gzip.compress(payload, compresslevel=6)
        telemetry_path = f"{sim_id}/telemetry.json.gz"

        supabase.storage.from_(BUCKET).upload(
            path=telemetry_path,
            file=gz,
            file_options={"content-type": "application/json", "upsert": "true"},
        )

        # ── graphs ────────────────────────────────────────────────
        chart_paths: list[str] = []
        for fname, png in render_graphs(history):
            chart_path = f"{sim_id}/graphs/{fname}"
            supabase.storage.from_(BUCKET).upload(
                path=chart_path,
                file=png,
                file_options={"content-type": "image/png", "upsert": "true"},
            )
            chart_paths.append(chart_path)

        # ── DB row (upsert on sim_id) ─────────────────────────────
        row: dict[str, Any] = {
            "sim_id": sim_id,
            "status": status,
            "config": config,
            "summary": summary,
            "file_path": telemetry_path,
            "route_name": route_name,
            "rider_ref": rider_ref,
            "stop_reason": stop_reason,
            "created_at": created_at,
        }
        if status in ("complete", "stopped"):
            from datetime import datetime, timezone
            row["completed_at"] = datetime.now(timezone.utc).isoformat()

        supabase.table("simulations").upsert(row, on_conflict="sim_id").execute()

    except Exception:
        logger.exception("Failed to persist simulation %s", sim_id)


def load_persisted(sim_id: str) -> dict[str, Any] | None:
    """Load a completed simulation from the DB + Storage.

    Returns a dict with keys: row, points (list[TelemetryPoint]).
    Returns None if not found.
    """
    try:
        resp = supabase.table("simulations").select("*").eq("sim_id", sim_id).execute()
    except Exception:
        logger.exception("DB read failed for %s", sim_id)
        return None

    rows = resp.data or []
    if not rows:
        return None

    row = rows[0]
    file_path = row.get("file_path")
    points: list[TelemetryPoint] = []

    if file_path:
        try:
            raw = supabase.storage.from_(BUCKET).download(file_path)
            if isinstance(raw, str):
                raw = raw.encode()
            data = json.loads(gzip.decompress(raw))
            points = [TelemetryPoint.model_validate(p) for p in data]
        except Exception:
            logger.exception("Telemetry download failed for %s", sim_id)

    return {"row": row, "points": points}


def delete_persisted(sim_id: str) -> bool:
    """Best-effort removal of DB row + Storage files."""
    removed = False

    # delete storage objects (folder contents)
    try:
        files = supabase.storage.from_(BUCKET).list(path=sim_id)
        paths = [f"{sim_id}/{f['name']}" for f in files] if files else []
        # also list graphs subfolder
        graph_files = supabase.storage.from_(BUCKET).list(path=f"{sim_id}/graphs")
        paths += [f"{sim_id}/graphs/{f['name']}" for f in graph_files] if graph_files else []
        if paths:
            supabase.storage.from_(BUCKET).remove(paths)
    except Exception:
        logger.exception("Storage cleanup failed for %s", sim_id)

    # delete DB row
    try:
        supabase.table("simulations").delete().eq("sim_id", sim_id).execute()
        removed = True
    except Exception:
        logger.exception("DB delete failed for %s", sim_id)

    return removed
