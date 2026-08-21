from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db import supabase

router = APIRouter(prefix='/riders', tags=['Riders'])

class RiderCreate(BaseModel):
    name: str
    mass: float
    bike_mass: float
    ftp: float
    f_max: float
    cda: float
    crr: float
    inertia: float
    wheel_radius: float
    metabolic_efficiency: float

@router.get('')
async def list_riders():
    response = (supabase.table('riders').select('*').execute())
    return response.data

@router.post('')
async def create_rider(rider: RiderCreate):
    response = supabase.table('riders').insert(rider.model_dump()).execute()
    if not response.data:
        raise HTTPException(
            status_code=500,
            detail="Rider could not be created",
        )
    return response.data[0]

@router.put('/{rider_name}')
async def update_rider(rider_name: str, rider: RiderCreate):
    response = supabase.table('riders').update(rider.model_dump()).eq('name', rider_name).execute()
    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Rider not found",
        )
    return response.data[0]

@router.get('/{rider_name}')
async def get_rider(rider_name: str):
    response = supabase.table('riders').select('*').eq('name', rider_name).execute()
    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Rider not found",
        )
    return response.data[0]


@router.delete('/{rider_name}')
async def delete_rider(rider_name: str):
    response = supabase.table('riders').delete().eq('name', rider_name).execute()
    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Rider not found",
        )
    return {"message": "Rider deleted successfully"}