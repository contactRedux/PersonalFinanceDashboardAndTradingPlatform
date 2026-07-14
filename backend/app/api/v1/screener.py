"""Screener endpoints — full implementation in ST-10."""
from fastapi import APIRouter

from app.dependencies import CurrentUser

router = APIRouter()


@router.post("/run")
async def run_screener(_: CurrentUser):
    return {"results": [], "note": "Screener engine in ST-10"}


@router.get("/presets")
async def get_presets(_: CurrentUser):
    return {"presets": []}


@router.post("/presets")
async def save_preset(_: CurrentUser):
    return {"note": "Save preset in ST-10"}
