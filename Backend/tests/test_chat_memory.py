import hmac
import json
import os
import sys
import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import redis

from test_rag import ROOT, dependency, load_module


class HashTests(unittest.TestCase):
    def test_stable_hmac_and_missing_secret(self):
        module = load_module('hash_under_test', 'Services/hash/hash.py', {
            'dotenv': dependency('dotenv', load_dotenv=MagicMock()),
        })
        with patch.dict(os.environ, {'SECRET_KEY': 'test-secret'}):
            expected = hmac.new(b'test-secret', b'127.0.0.1', 'sha256').hexdigest()
            self.assertEqual(module.encrypted('127.0.0.1'), expected)
            self.assertEqual(module.encrypted('2001:db8::1'), module.encrypted('2001:0db8:0:0:0:0:0:1'))
            self.assertNotEqual(module.encrypted('127.0.0.2'), expected)
        with patch.dict(os.environ, {'SECRET_KEY': ''}):
            with self.assertRaises(ValueError):
                module.encrypted('127.0.0.1')


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module('store_under_test', 'Services/redis/redis.py', {
            'dotenv': dependency('dotenv', load_dotenv=MagicMock()),
        })
        self.client = MagicMock()
        self.pipe = self.client.pipeline.return_value.__enter__.return_value
        self.store = self.module.ChatStore(self.client)

    def test_new_id_is_uuid_and_owner_is_saved(self):
        from uuid import UUID
        self.client.set.return_value = True
        chat_id = self.store.create_chat('hashed-ip')
        UUID(chat_id)
        self.client.set.assert_called_once_with(self.store.keys(chat_id)[0], 'hashed-ip', nx=True)

    def test_list_chats_returns_only_owned_chats_and_last_question(self):
        mine = '59e2b4b1-89ec-4fb6-b897-24cd93276613'
        other = 'd6fd12de-55d5-47fd-b577-ccf272389c04'
        mine_key, _ = self.store.keys(mine)
        other_key, _ = self.store.keys(other)
        self.client.scan_iter.return_value = [mine_key, other_key, mine_key]
        self.client.get.side_effect = lambda key: 'owner' if key == mine_key else 'other'
        self.store.snapshot = MagicMock(return_value=([
            {'role': 'user', 'content': 'Última pergunta: e agora?'},
            {'role': 'assistant', 'content': 'Resposta privada'},
        ], 6))
        self.assertEqual(self.store.list_chats('owner'), [
            {'chat_id': mine, 'last_question': 'Última pergunta: e agora?'},
        ])
        self.store.snapshot.assert_called_once_with('owner', mine, limit=2)

    def test_list_chats_ignores_empty_and_disappeared_chats(self):
        first = '59e2b4b1-89ec-4fb6-b897-24cd93276613'
        second = 'd6fd12de-55d5-47fd-b577-ccf272389c04'
        self.client.scan_iter.return_value = [self.store.keys(first)[0], self.store.keys(second)[0]]
        self.client.get.return_value = 'owner'
        self.store.snapshot = MagicMock(side_effect=[([], 0), self.module.ChatNotFoundError()])
        self.assertEqual(self.store.list_chats('owner'), [])

    def test_list_chats_empty_database(self):
        self.client.scan_iter.return_value = []
        self.assertEqual(self.store.list_chats('owner'), [])

    def test_history_preserves_json_colons_and_newlines(self):
        record = {'role': 'user', 'content': 'Site: https://example.com\nOutra linha'}
        self.pipe.execute.return_value = ['owner', 2, [json.dumps(record)]]
        history, version = self.store.snapshot('owner', 'id')
        self.assertEqual(history, [record])
        self.assertEqual(version, 2)
        self.pipe.lrange.assert_called_once_with(self.store.keys('id')[1], -20, -1)

    def test_other_user_cannot_read_or_write(self):
        self.pipe.execute.return_value = ['another-owner', 0, []]
        with self.assertRaises(self.module.ChatNotFoundError):
            self.store.snapshot('owner', 'id')
        self.pipe.get.return_value = 'another-owner'
        with self.assertRaises(self.module.ChatNotFoundError):
            self.store.save_turn('owner', 'id', 'question', 'answer', 0)
        self.pipe.rpush.assert_not_called()

    def test_turn_appends_both_roles_in_single_command(self):
        self.pipe.get.return_value = 'owner'
        self.pipe.llen.return_value = 2
        self.store.save_turn('owner', 'id', 'Pergunta: olá', 'Resposta\nBraille', 2)
        arguments = self.pipe.rpush.call_args.args
        self.assertEqual(arguments[0], self.store.keys('id')[1])
        self.assertEqual([json.loads(record) for record in arguments[1:]], [
            {'role': 'user', 'content': 'Pergunta: olá'},
            {'role': 'assistant', 'content': 'Resposta\nBraille'},
        ])
        self.pipe.multi.assert_called_once()
        self.pipe.execute.assert_called_once()

    def test_concurrent_update_is_not_overwritten(self):
        self.pipe.get.return_value = 'owner'
        self.pipe.llen.return_value = 4
        with self.assertRaises(self.module.ConcurrentChatError):
            self.store.save_turn('owner', 'id', 'question', 'answer', 2)
        self.pipe.rpush.assert_not_called()
        self.pipe.llen.return_value = 2
        self.pipe.execute.side_effect = self.module.redis.WatchError()
        with self.assertRaises(self.module.ConcurrentChatError):
            self.store.save_turn('owner', 'id', 'question', 'answer', 2)


class ControllerMemoryTests(unittest.TestCase):
    def setUp(self):
        self.generate = MagicMock(return_value='Resposta da LLM')
        self.path_patch = patch.object(sys, 'path', [str(ROOT), *sys.path])
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        self.controller = load_module('controller_under_test', 'Controllers/LLM/coordinatorController.py', {
            'Agents.coordinatorAgent': dependency('coordinator', coordinator_agent=self.generate),
        })
        self.hash = patch.object(self.controller, 'encrypted', return_value='hashed-ip').start()
        self.addCleanup(patch.stopall)
        self.store = MagicMock()
        self.chat_id = '59e2b4b1-89ec-4fb6-b897-24cd93276613'
        self.store.create_chat.return_value = self.chat_id
        self.store.snapshot.return_value = ([], 0)
        patch.object(self.controller, 'ChatStore', return_value=self.store).start()
        self.request = SimpleNamespace(client=SimpleNamespace(host='127.0.0.1'),
                                       app=SimpleNamespace(state=SimpleNamespace(llm={})))

    def test_new_chat_and_followup_reuse_id_and_history(self):
        first = self.controller.chat(self.controller.ChatRequest(search='Pergunta'), self.request)
        self.assertEqual(first['chat_id'], self.chat_id)
        self.hash.assert_called_with('127.0.0.1')
        self.store.save_turn.assert_called_with('hashed-ip', self.chat_id, 'Pergunta', 'Resposta da LLM', expected_version=0)
        history = [{'role': 'user', 'content': 'Pergunta'}, {'role': 'assistant', 'content': 'Resposta da LLM'}]
        self.store.snapshot.return_value = (history, 2)
        second = self.controller.chat(self.controller.ChatRequest(search='E onde?', chat_id=self.chat_id), self.request)
        self.assertEqual(second['chat_id'], self.chat_id)
        self.store.create_chat.assert_called_once()
        self.generate.assert_called_with(llm={}, query='E onde?', history=history)
        self.store.save_turn.assert_called_with('hashed-ip', self.chat_id, 'E onde?', 'Resposta da LLM', expected_version=2)

    def test_missing_or_foreign_chat_never_reaches_model(self):
        self.store.snapshot.side_effect = self.controller.ChatNotFoundError()
        with self.assertRaises(self.controller.HTTPException) as caught:
            self.controller.chat(self.controller.ChatRequest(search='Pergunta', chat_id=self.chat_id), self.request)
        self.assertEqual(caught.exception.status_code, 404)
        self.generate.assert_not_called()
        self.store.save_turn.assert_not_called()

    def test_current_url_is_passed_to_agent_and_stored(self):
        url = 'https://www.puc-campinas.edu.br/sistemas-de-informacao/'
        body = self.controller.ChatRequest(search='O que tem neste curso?', url=url)
        self.controller.chat(body, self.request)
        self.generate.assert_called_with(llm={}, query='O que tem neste curso?', history=[], current_url=url)
        self.store.save_turn.assert_called_with('hashed-ip', self.chat_id, 'O que tem neste curso?',
                                                'Resposta da LLM', expected_version=0, current_url=url)

    def test_non_http_current_url_is_rejected(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            self.controller.ChatRequest(search='Pergunta', url='javascript:alert(1)')

    def test_storage_failure_and_conflict_are_explicit(self):
        for error, expected in [(self.controller.RedisError(), 503), (self.controller.ConcurrentChatError(), 409)]:
            self.store.save_turn.side_effect = error
            with self.assertRaises(self.controller.HTTPException) as caught:
                with self.assertLogs(self.controller.__name__, level='ERROR') if expected == 503 else nullcontext():
                    self.controller.chat(self.controller.ChatRequest(search='Pergunta', chat_id=self.chat_id), self.request)
            self.assertEqual(caught.exception.status_code, expected)

    def test_failed_generation_does_not_save_incomplete_turn(self):
        self.generate.side_effect = RuntimeError('generation failed')
        with self.assertRaises(RuntimeError):
            self.controller.chat(self.controller.ChatRequest(search='Pergunta'), self.request)
        self.store.save_turn.assert_not_called()


if __name__ == '__main__':
    unittest.main()
