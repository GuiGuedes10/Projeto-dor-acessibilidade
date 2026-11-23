from fastapi import APIRouter, Request
from Controllers.chromaDb.searchData import search_data

router = APIRouter()

@router.post("/searchData")
async def prompt(request: Request):
    return await search_data(request)