from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from db import supabase
from engine.route import Route

router = APIRouter(prefix="/routes", tags=["Routes"])

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
        raise HTTPException(
            status_code=404,
            detail="Route not found",
        )
    return data[0]


@router.post("")
async def upload_route(
    name: str = Form(...),
    file: UploadFile = File(...),
):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="A file name is required",
        )

    if Path(file.filename).suffix.lower() != ".gpx":
        raise HTTPException(
            status_code=400,
            detail="Only .gpx files are accepted",
        )

    contents = await file.read()

    if not contents:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty",
        )

    route_id = str(uuid4())
    file_path = f"routes/{route_id}/original.gpx"

    try:
        supabase.storage.from_(GPX_BUCKET).upload(
            path=file_path,
            file=contents,
            file_options={
                "content-type": "application/gpx+xml",
                "upsert": "false",
            },
        )

        result = (
            supabase
            .table("routes")
            .insert({
                "name": name,
                "file_path": file_path,
            })
            .execute()
        )

        if not result.data:
            raise RuntimeError("No route record was returned")

        return result.data[0]

    except Exception as exc:
        # Avoid leaving an orphaned Storage object if the metadata insert fails.
        try:
            supabase.storage.from_(GPX_BUCKET).remove([file_path])
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail=f"Route upload failed: {exc}",
        ) from exc

@router.get("")
async def list_routes():
    response = supabase.table("routes").select("id, name, file_path, created_at").order("created_at", desc=True).execute()
    return response.data or []


@router.get('/{route_ref}')
async def get_route(route_ref: str):
    return _fetch_route_row(route_ref)


@router.get('/{route_ref}/points')
async def get_route_geometry(route_ref: str):
    row = _fetch_route_row(route_ref)
    file_path = row.get("file_path")
    if not file_path:
        raise HTTPException(
            status_code=404,
            detail="Route has no GPX file",
        )

    try:
        data = supabase.storage.from_(GPX_BUCKET).download(file_path)
        if isinstance(data, str):
            data = data.encode()
        route = Route.get_route_from_bytes(data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not load route geometry: {exc}",
        ) from exc

    if len(route.points) < 2:
        raise HTTPException(
            status_code=422,
            detail="Route contains fewer than 2 points",
        )

    gain, loss = route.elevation_stats()
    points = route.geometry()

    return {
        "id": str(row.get("id")),
        "name": row.get("name"),
        "distance": round(points[-1]["distance"], 3),
        "elevationGain": round(gain, 1),
        "elevationLoss": round(loss, 1),
        "maxElevation": round(max(p["elevation"] for p in points), 1),
        "minElevation": round(min(p["elevation"] for p in points), 1),
        "uploadedAt": row.get("created_at"),
        "source": "upload",
        "points": points,
    }

@router.delete('/{route_name}')
async def delete_route(route_name: str):
    response = supabase.table('routes').select('*').eq('name', route_name).execute()
    if not response.data:
        raise HTTPException(
            status_code=404,
            detail='Route not found',
        )

    return response.data[0]