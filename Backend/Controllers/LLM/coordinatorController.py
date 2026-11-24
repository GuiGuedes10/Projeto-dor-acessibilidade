import logging
from uuid import UUID

from fastapi import Request, HTTPException
from pydantic import BaseModel, Field, field_validator
from redis.exceptions import RedisError

from Agents.coordinatorAgent import coordinator_agent
from Services.hash.hash import encrypted
from Services.redis.redis import ChatStore, ChatNotFoundError, ConcurrentChatError


class ChatRequest(BaseModel):
    search: str = Field(min_length=1)
    chat_id: UUID | None = None

    @field_validator('search')
    @classmethod
    def validate_search(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('A pergunta não pode estar vazia.')
        return value.strip()


def chat(body: ChatRequest, request: Request):
    query = body.search.strip()
    if request.client is None:
        raise HTTPException(400, 'Não foi possível identificar o endereço do cliente.')
    try:
        user_id = encrypted(request.client.host)
        store = ChatStore()
        chat_id = str(body.chat_id) if body.chat_id else store.create_chat(user_id)
        history, version = store.snapshot(user_id, chat_id)
        response = coordinator_agent(llm=request.app.state.llm, query=query, history=history)
        store.save_turn(user_id, chat_id, query, response, expected_version=version)
    except ChatNotFoundError:
        raise HTTPException(404, 'Conversa não encontrada.')
    except ConcurrentChatError:
        raise HTTPException(409, 'A conversa recebeu outra mensagem. Envie novamente.')
    except (RedisError, ValueError):
        logging.getLogger(__name__).exception('Falha na configuração ou persistência da conversa')
        raise HTTPException(503, 'Memória de conversa indisponível. Tente novamente mais tarde.')
    return {'chat_id': chat_id, 'query': query, 'response': response}
