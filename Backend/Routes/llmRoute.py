from fastapi import APIRouter, Request
from uuid import UUID

from Controllers.LLM.ragController import RagRequest, test_rag
from Controllers.LLM.coordinatorController import ChatRequest, chat
from Controllers.LLM.chatHistoryController import ChatSummary, ChatConversation, list_user_chats, get_user_chat

router = APIRouter()


@router.get("/chats", response_model=list[ChatSummary])
def user_chats(request: Request):
    return list_user_chats(request)


@router.get("/chats/{chat_id}", response_model=ChatConversation, response_model_exclude_none=True)
def user_chat(chat_id: UUID, request: Request):
    return get_user_chat(chat_id, request)


@router.post("/chat")
def coordinator_chat(body: ChatRequest, request: Request):
    return chat(body, request)


@router.post("/rag")
def rag_test(body: RagRequest, request: Request):
    return test_rag(body, request)
