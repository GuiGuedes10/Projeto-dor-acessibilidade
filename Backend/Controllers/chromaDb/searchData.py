from fastapi import Request
from Utils.errors import ApiError
from Services.orm.search import search_knowledge_base

async def search_data(request: Request):
    
    try:
        body = await request.json()
    except Exception:
        raise ApiError(400, "invalid_request", "Payload JSON inválido.")
    
    search = body.get("search")

    if not isinstance(search, str) or not search.strip():
        raise ApiError(400, "text_too_short", "O campo 'request' é obrigatório e não pode estar vazio.")

    results = search_knowledge_base(
        search,
        top_k=5
    )

    return results