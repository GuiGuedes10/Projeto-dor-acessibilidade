from fastapi import APIRouter, Request

from Controllers.LLM.ragController import RagRequest, test_rag
from Controllers.LLM.coordinatorController import ChatRequest, chat

router = APIRouter()


@router.post("/memory")
def coordinator_chat(body: ChatRequest, request: Request):
    return chat(body, request)
