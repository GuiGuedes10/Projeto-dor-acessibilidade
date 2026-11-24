from fastapi import APIRouter, Request

from Controllers.LLM.ragController import RagRequest, test_rag
from Controllers.LLM.coordinatorController import ChatRequest, chat
from Controllers.LLM.chatHistoryController import ChatSummary, list_user_chats

router = APIRouter()


@router.get("/chats", response_model=list[ChatSummary])
def user_chats(request: Request):
    return list_user_chats(request)


@router.post("/chat")
def coordinator_chat(body: ChatRequest, request: Request):
    return chat(body, request)


@router.post("/rag")
def rag_test(body: RagRequest, request: Request):
    return test_rag(body, request)
