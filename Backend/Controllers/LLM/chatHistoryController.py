import logging

from fastapi import HTTPException, Request
from pydantic import BaseModel
from redis.exceptions import RedisError

from Services.hash.hash import encrypted
from Services.redis.redis import ChatStore


class ChatSummary(BaseModel):
    chat_id: str
    last_question: str


def list_user_chats(request: Request):
    if request.client is None:
        raise HTTPException(400, 'Não foi possível identificar o endereço do cliente.')
    try:
        user_id = encrypted(request.client.host)
        return ChatStore().list_chats(user_id)
    except (RedisError, ValueError):
        logging.getLogger(__name__).exception('Não foi possível listar as conversas')
        raise HTTPException(503, 'Memória de conversa indisponível. Tente novamente mais tarde.')
