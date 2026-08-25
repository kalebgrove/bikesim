import asyncio
import json

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from db import supabase
from engine.route import Route
from schemas import (
    RiderConfig,
    SimulationCreated,
    SimulationState,
    SimCreateRequest,
    SimSummary,
)
from sim_manager import manager, rider_from_config
from persistence import delete_persisted, load_persisted, persist_session

router = APIRouter(prefix="/simulations", tags=["Simulations"])

GPX_BUCKET = "gpx_files"


def _fetch_route_row(route_ref: str) -> dict:
    data = []
    if route_ref.isdigit():
        response = supabase.table("routes").select("*").eq("id", int(route_ref)).execute()
        data = response.data or []
    if not data:
        response = supabase.table("routes").select("*").eq("name", route_ref).execute()
        data = response.data or []
    if not data:
        raise HTTPException(status_code=404, detail=f"Route '{route_ref}' not found")
    return data[0]


def _fetch_rider_row(rider_ref: str) -> dict:
    data = []
    if rider_ref.isdigit():
        response = supabase.table("riders").select("*").eq("id", int(rider_ref)).execute()
        data = response.data or []
    if not data:
        response = supabase.table("riders").select("*").eq("name", rider_ref).execute()
        data = response.data or []
    if not data:
        raise HTTPException(status_code=404, detail=f"Rider '{rider_ref}' not found")
    return data[0]


def _download_gpx(file_path: str) -> Route:
    data = supabase.storage.from_(GPX_BUCKET).download(file_path)
    if isinstance(data, str):
        data = data.encode()
    return Route.get_route_from_bytes(data)


@router.post("")
async def create_simulation(req: SimCreateRequest):
    route_row = _fetch_route_row(req.config.routeId)
    route = _download_gpx(route_row["file_path"])

    if req.config.rider is not None:
        rider = rider_from_config(req.config.rider)
    elif req.riderId is not None:
        rider_row = _fetch_rider_row(req.riderId)
        rider = rider_from_config(RiderConfig(
            mass=rider_row.get("mass", 0) + rider_row.get("bike_mass", 0),
            ftp=rider_row["ftp"],
            cda=rider_row["cda"],
            crr=rider_row["crr"],
        ))
    else:
        raise HTTPException(status_code=422, detail="Provide either 'config.rider' or 'riderId'")

    session = manager.create(rider, route, req.config)

    return SimulationCreated(
        simId=session.id,
        status=session.status,
        createdAt=session.created_at,
        routeName=route_row.get("name") or req.config.routeId,
        totalDistanceKm=round(session.total_distance_m / 1000, 3),
    )


@router.get("/{sim_id}")
async def get_simulation(sim_id: str):
    session = manager.get(sim_id)
    if session is not None:
        return SimulationState(
            simId=session.id,
            status=session.status,
            tickCount=len(session.history),
            latest=session.history[-1] if session.history else None,
            summary=session.summary() if session.status in ("complete", "stopped") else None,
        )

    persisted = await asyncio.to_thread(load_persisted, sim_id)
    if persisted is None:
        raise HTTPException(status_code=404, detail="Simulation not found")

    row = persisted["row"]
    points = persisted["points"]
    summary = SimSummary.model_validate(row["summary"]) if row.get("summary") else None
    return SimulationState(
        simId=sim_id,
        status=row["status"],
        tickCount=len(points),
        latest=points[-1] if points else None,
        summary=summary,
    )


@router.delete("/{sim_id}")
async def delete_simulation(sim_id: str):
    session = manager.get(sim_id)
    if session is not None:
        session.stop("Deleted")
        manager.delete(sim_id)
    await asyncio.to_thread(delete_persisted, sim_id)
    return {"message": f"Simulation {sim_id} deleted"}


@router.websocket("/{sim_id}/stream")
async def stream_simulation(ws: WebSocket, sim_id: str):
    session = manager.get(sim_id)
    if session is None:
        await ws.close(code=4404)
        return

    # Resolve route name once for persistence (best-effort).
    route_name = session.config.routeId
    try:
        route_row = _fetch_route_row(session.config.routeId)
        route_name = route_row.get("name", route_name)
    except Exception:
        pass

    await ws.accept()
    await ws.send_json({"type": "status", "data": {"simId": sim_id, "status": session.status}})

    tick_interval_s = max(0.016, session.config.simSettings.tickIntervalMs / 1000)

    async def receive_controls():
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                kind = message.get("type")
                if kind == "pause":
                    session.pause()
                    await ws.send_json({"type": "status", "data": {"simId": sim_id, "status": session.status}})
                elif kind == "resume":
                    session.resume()
                    await ws.send_json({"type": "status", "data": {"simId": sim_id, "status": session.status}})
                elif kind == "stop":
                    session.stop(message.get("reason"))
                elif kind == "restart":
                    session.restart()
                    await ws.send_json({"type": "status", "data": {"simId": sim_id, "status": session.status}})
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    controls_task = asyncio.create_task(receive_controls())

    try:
        while True:
            if session.status == "paused":
                await asyncio.sleep(0.05)
                continue
            if session.status != "running":
                break

            point = await asyncio.to_thread(session.tick)
            if point is None:
                break
            await ws.send_json({"type": "tick", "data": point.model_dump()})
            if session.status == "running":
                await asyncio.sleep(tick_interval_s)

        if session.status == "complete":
            summary = await asyncio.to_thread(session.summary)
            await ws.send_json({"type": "summary", "data": summary.model_dump()})
        elif session.status == "stopped":
            await ws.send_json({"type": "stopped", "data": {"reason": session.stop_reason}})

        # Fire-and-forget: persist telemetry + charts without blocking WS close.
        if session.status in ("complete", "stopped"):
            hist_snapshot = list(session.history)
            summary_snapshot = session.summary().model_dump()

            async def _persist_bg() -> None:
                await asyncio.to_thread(
                    persist_session,
                    sim_id=sim_id,
                    route_name=route_name,
                    rider_ref=None,
                    status=session.status,
                    stop_reason=session.stop_reason,
                    config=session.config.model_dump(),
                    summary=summary_snapshot,
                    history=hist_snapshot,
                    created_at=session.created_at,
                )
            asyncio.ensure_future(_persist_bg())
    except WebSocketDisconnect:
        pass
    finally:
        controls_task.cancel()
        try:
            await controls_task
        except (asyncio.CancelledError, Exception):
            pass
        await ws.close()
