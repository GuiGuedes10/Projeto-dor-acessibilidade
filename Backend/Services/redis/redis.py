import json
import os
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

import redis
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / '.env')


class ChatNotFoundError(Exception):
    pass


class ConcurrentChatError(Exception):
    pass


@lru_cache(maxsize=1)
def get_client():
    options = {'decode_responses': True, 'socket_connect_timeout': 3, 'socket_timeout': 3}
    if os.getenv('REDIS_URL'):
        return redis.Redis.from_url(os.environ['REDIS_URL'], **options)
    return redis.Redis(host=os.getenv('REDIS_HOST') or os.getenv('HOST', 'localhost'),
                       port=int(os.getenv('REDIS_PORT', '6379')),
                       db=int(os.getenv('REDIS_DB', '0')),
                       password=os.getenv('REDIS_PASSWORD') or None, **options)


class ChatStore:
    def __init__(self, client=None):
        self.client = client if client is not None else get_client()

    @staticmethod
    def keys(chat_id):
        return f'chat:{{{chat_id}}}:user_id', f'chat:{{{chat_id}}}:messages'

    def create_chat(self, user_id: str) -> str:
        for _ in range(3):
            chat_id = str(uuid4())
            owner_key, _ = self.keys(chat_id)
            if self.client.set(owner_key, user_id, nx=True):
                return chat_id
        raise RuntimeError('Não foi possível gerar um ID de conversa único.')

    def snapshot(self, user_id: str, chat_id: str, limit: int | None = 20):
        if limit is not None and limit < 1:
            raise ValueError('O limite de histórico deve ser positivo.')
        owner_key, messages_key = self.keys(chat_id)
        with self.client.pipeline(transaction=True) as pipe:
            pipe.get(owner_key)
            pipe.llen(messages_key)
            pipe.lrange(messages_key, -limit if limit is not None else 0, -1)
            owner, version, messages = pipe.execute()
        if owner != user_id:
            raise ChatNotFoundError('Conversa não encontrada.')
        return [json.loads(message) for message in messages], version

    def list_chats(self, user_id: str) -> list[dict]:
        from uuid import UUID

        summaries = []
        seen = set()
        for owner_key in self.client.scan_iter(match='chat:{*}:user_id', count=100):
            # SCAN pode devolver a mesma chave mais de uma vez.
            if owner_key in seen:
                continue
            seen.add(owner_key)
            if self.client.get(owner_key) != user_id:
                continue
            try:
                chat_id = str(UUID(owner_key[len('chat:{'):-len('}:user_id')]))
            except ValueError:
                continue
            try:
                messages, _ = self.snapshot(user_id, chat_id, limit=2)
            except ChatNotFoundError:
                continue
            question = next((message['content'] for message in reversed(messages)
                             if message.get('role') == 'user'), None)
            if question is not None:
                summaries.append({'chat_id': chat_id, 'last_question': question})
        return sorted(summaries, key=lambda item: item['chat_id'])

    def save_turn(self, user_id: str, chat_id: str, user_message: str,
                  llm_response: str, expected_version: int, *, current_url: str | None = None):
        owner_key, messages_key = self.keys(chat_id)
        messages = [json.dumps({'role': role, 'content': content,
                                **({'url': current_url} if role == 'user' and current_url else {})}, ensure_ascii=False)
                    for role, content in [('user', user_message), ('assistant', llm_response)]]
        try:
            with self.client.pipeline() as pipe:
                pipe.watch(owner_key, messages_key)
                if pipe.get(owner_key) != user_id:
                    raise ChatNotFoundError('Conversa não encontrada.')
                if pipe.llen(messages_key) != expected_version:
                    raise ConcurrentChatError('A conversa recebeu outra mensagem. Tente novamente.')
                pipe.multi()
                # Pergunta e resposta são gravadas juntas, sem sobrescrever o histórico.
                pipe.rpush(messages_key, *messages)
                pipe.execute()
        except redis.WatchError as error:
            raise ConcurrentChatError('A conversa recebeu outra mensagem. Tente novamente.') from error


def save_chat(user_id: str, chat_id: str, user_message: str, llm_response: str,
              *, expected_version: int):
    ChatStore().save_turn(user_id, chat_id, user_message, llm_response, expected_version)


def get_chat_history(user_id: str, chat_id: str):
    return ChatStore().snapshot(user_id, chat_id, limit=None)[0]
