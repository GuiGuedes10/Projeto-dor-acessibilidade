import json
import sys
import unittest
from unittest.mock import MagicMock, patch

from test_rag import ROOT, dependency, load_module


class ToolExecutionTests(unittest.TestCase):
    def setUp(self):
        self.engine = load_module('engine_under_test', 'Services/agents/specialist_agent.py', {
            'torch': dependency('torch'),
        })
        self.turn = MagicMock()
        self.engine.generate_turn = self.turn
        self.executed = []

        def lookup(query: str) -> str:
            self.executed.append(query)
            return 'Há livros em Braille. [1] guia.pdf, página 12'
        self.tool = lookup

    def call(self, name='lookup', arguments=None):
        return '<tool_call>' + json.dumps({'name': name, 'arguments': arguments or {'query': 'Braille?'}}) + '</tool_call>'

    def test_direct_response_does_not_execute_tools(self):
        self.turn.return_value = 'Olá! Como posso ajudar?'
        self.assertIn('Olá', self.engine.generate_response({}, 'oi', [self.tool]))
        self.assertEqual(self.executed, [])

    def test_unverified_coordinator_answer_is_discarded(self):
        self.turn.return_value = 'Yes, SBI means São Bento Institute.'
        answer = self.engine.generate_response({}, 'SBI?', [self.tool], fallback_tool=self.tool)
        self.assertEqual(self.executed, ['SBI?'])
        self.assertIn('Braille', answer)
        self.assertNotIn('São Bento', answer)

    def test_specialist_response_is_not_rewritten(self):
        self.turn.side_effect = [self.call(), 'Invented institution']
        answer = self.engine.generate_response({}, 'SBI?', [self.tool], return_direct_tools=('lookup',))
        self.assertEqual(self.turn.call_count, 1)
        self.assertIn('guia.pdf', answer)
        self.assertNotIn('Invented', answer)

    def test_tool_result_is_delivered_to_model(self):
        self.turn.side_effect = [self.call(), 'Sim, há Braille. [1] guia.pdf, página 12']
        response = self.engine.generate_response({}, 'Braille?', [self.tool], system_prompt='Regras')
        self.assertEqual(self.executed, ['Braille?'])
        history = self.turn.call_args.args[1]
        self.assertEqual(history[0]['role'], 'system')
        self.assertEqual(history[-1]['role'], 'tool')
        self.assertIn('guia.pdf', history[-1]['content'])
        self.assertIn('guia.pdf', response)

    def test_invalid_unknown_and_wrong_arguments_do_not_crash(self):
        for response in ['<tool_call>invalid</tool_call>', self.call('unknown'),
                         self.call(arguments={'unexpected': 'x'})]:
            self.turn.side_effect = [response, 'Não foi possível consultar.']
            self.engine.generate_response({}, 'teste', [self.tool])
        self.assertEqual(self.executed, [])

    def test_batch_cannot_bypass_call_budget(self):
        self.turn.side_effect = [self.call() * 5, 'Resultado disponível.']
        self.engine.generate_response({}, 'teste', [self.tool], max_iterations=1)
        self.assertEqual(len(self.executed), 1)
        self.assertEqual(self.turn.call_args.args[2], [])

    def test_repeated_tool_calls_stop(self):
        self.turn.return_value = self.call()
        response = self.engine.generate_response({}, 'teste', [self.tool], max_iterations=2)
        self.assertEqual(len(self.executed), 2)
        self.assertIn('Limite', response)

    def test_tool_exception_is_reported_without_exposing_exception(self):
        def broken(query: str):
            raise RuntimeError('internal details')
        self.turn.side_effect = [self.call('broken'), 'A consulta falhou.']
        with self.assertLogs(self.engine.logger, level='ERROR'):
            self.engine.generate_response({}, 'teste', [broken])
        result = self.turn.call_args.args[1][-1]['content']
        self.assertIn('Erro', result)
        self.assertNotIn('internal details', result)


class CoordinatorTests(unittest.TestCase):
    def test_binds_rag_model_and_registers_extra_tool(self):
        generate = MagicMock(return_value='Resposta')
        rag = MagicMock(return_value='Braille [1]')
        model = {'model': object()}
        tools = load_module('tools_under_test', 'Services/tools/agent_tools.py', {})
        coordinator = load_module('coordinator_under_test', 'Agents/coordinatorAgent.py', {
            'Services.agents.specialist_agent': dependency('engine', generate_response=generate),
            'Services.tools.agent_tools': dependency('tools', build_rag_tool=tools.build_rag_tool),
        })
        def other_tool(value: str) -> str:
            return value
        self.assertEqual(coordinator.coordinator_agent(model, ' Pergunta ', extra_tools=[other_tool]), 'Resposta')
        kwargs = generate.call_args.kwargs
        self.assertEqual(kwargs['prompt'], 'Pergunta')
        self.assertEqual(kwargs['tools'][1], other_tool)
        with patch.dict(sys.modules, {'Agents.ragAgent': dependency('rag', rag_agent=rag)}):
            self.assertEqual(kwargs['tools'][0](query=' Braille? '), 'Braille [1]')
        rag.assert_called_once_with(model, 'Braille?')

    def test_chat_route_uses_coordinator_and_keeps_rag_endpoint(self):
        coordinator, rag = MagicMock(return_value='Coordenado'), MagicMock(return_value='Especialista')
        with patch.object(sys, 'path', [str(ROOT), *sys.path]), patch.dict(sys.modules, {
            'Agents.coordinatorAgent': dependency('coordinator', coordinator_agent=coordinator),
            'Agents.ragAgent': dependency('rag', rag_agent=rag),
        }):
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            from Routes.llmRoute import router
            app = FastAPI()
            app.state.llm = {'model': 'test'}
            app.include_router(router, prefix='/llm')
            with TestClient(app) as client:
                response = client.post('/llm/chat', json={'search': ' oi '})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {'query': 'oi', 'response': 'Coordenado'})
                self.assertEqual(client.post('/llm/rag', json={'search': 'SBI?'}).json()['response'], 'Especialista')
                self.assertEqual(client.post('/llm/chat', json={}).status_code, 422)
                self.assertEqual(client.post('/llm/chat', json={'search': '   '}).status_code, 422)
            coordinator.assert_called_once_with(llm=app.state.llm, query='oi')


if __name__ == '__main__':
    unittest.main()
