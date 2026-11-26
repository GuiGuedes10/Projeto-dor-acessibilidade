import logging
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, Request
from pydantic import BaseModel
from redis.exceptions import RedisError

from Services.hash.hash import encrypted
from Services.redis.redis import ChatStore, ChatNotFoundError


class ChatSummary(BaseModel):
    chat_id: str
    last_question: str


class ChatMessage(BaseModel):
    role: Literal['user', 'assistant']
    content: str
    url: str | None = None


class ChatConversation(BaseModel):
    chat_id: UUID
    messages: list[ChatMessage]


def get_user_chat(chat_id: UUID, request: Request):
    if request.client is None:
        raise HTTPException(400, 'Não foi possível identificar o endereço do cliente.')
    try:
        user_id = encrypted(request.client.host)
        messages, _ = ChatStore().snapshot(user_id, str(chat_id), limit=None)
        return {'chat_id': str(chat_id), 'messages': messages}
    except ChatNotFoundError:
        raise HTTPException(404, 'Conversa não encontrada.')
    except (RedisError, ValueError):
        logging.getLogger(__name__).exception('Não foi possível recuperar a conversa')
        raise HTTPException(503, 'Memória de conversa indisponível. Tente novamente mais tarde.')


def list_user_chats(request: Request):
    if request.client is None:
        raise HTTPException(400, 'Não foi possível identificar o endereço do cliente.')
    try:
        user_id = encrypted(request.client.host)
        return ChatStore().list_chats(user_id)
    except (RedisError, ValueError):
        logging.getLogger(__name__).exception('Não foi possível listar as conversas')
        raise HTTPException(503, 'Memória de conversa indisponível. Tente novamente mais tarde.')
