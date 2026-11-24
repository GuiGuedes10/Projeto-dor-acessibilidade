from pathlib import Path
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exercise', action='store_true', help='Testa uma conversa temporária e remove apenas suas chaves ao terminar')
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from Services.redis.redis import get_client, ChatStore, ChatNotFoundError, ConcurrentChatError
    client = get_client()
    print('Redis conectado:', client.ping())
    if not args.exercise:
        return
    from uuid import uuid4
    store = ChatStore(client)
    user_id = 'integration-test-' + uuid4().hex
    chat_id = store.create_chat(user_id)
    try:
        history, version = store.snapshot(user_id, chat_id)
        assert history == [] and version == 0
        store.save_turn(user_id, chat_id, 'Pergunta: teste', 'Resposta\nlinha 2', version)
        history, version = store.snapshot(user_id, chat_id)
        assert version == 2 and history == [
            {'role': 'user', 'content': 'Pergunta: teste'},
            {'role': 'assistant', 'content': 'Resposta\nlinha 2'},
        ]
        try:
            store.snapshot('outro-usuario', chat_id)
        except ChatNotFoundError:
            pass
        else:
            raise AssertionError('Outro usuário conseguiu ler o histórico')
        try:
            store.save_turn(user_id, chat_id, 'Desatualizado', 'Resposta', 0)
        except ConcurrentChatError:
            pass
        else:
            raise AssertionError('Uma gravação desatualizada foi aceita')
        store.save_turn(user_id, chat_id, 'Continuação', 'Segunda resposta', version)
        assert store.snapshot(user_id, chat_id)[1] == 4
        assert store.list_chats(user_id) == [{'chat_id': chat_id, 'last_question': 'Continuação'}]
        print('Conversa, histórico, isolamento e conflito: OK')
    finally:
        client.delete(*store.keys(chat_id))
        print('Chaves temporárias removidas.')


if __name__ == '__main__':
    main()
