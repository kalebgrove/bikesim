from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from db import supabase

router = APIRouter(prefix="/routes", tags=["Routes"])

GPX_BUCKET = "gpx_files"


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

@router.get('/{route_name}')
async def get_route(route_name: str):
    response = supabase.table('routes').select('*').eq('name', route_name).execute()
    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Route not found",
        )
    return response.data[0]

@router.delete('/{route_name}')
async def delete_route(route_name: str):
    response = supabase.table('routes').select('*').eq('name', route_name).execute()
    if not response.data:
        raise HTTPException(
            status_code=404,
            detail='Route not found',
        )

    return response.data[0]