import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from test_rag import ROOT, dependency, load_module

BASE = 'https://www.puc-campinas.edu.br/'
TARGET = BASE + 'sistemas-de-informacao/'


class GraphServiceTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.module = load_module('graph_under_test', 'Services/Neo4j/neo4j_service.py', {
            'dotenv': dependency('dotenv', load_dotenv=MagicMock()),
        })
        self.driver = MagicMock()
        self.driver.execute_query.return_value = ([], None, None)
        self.service = self.module.Neo4jService(self.driver)

    def records(self, rows):
        self.driver.execute_query.return_value = ([MagicMock(data=MagicMock(return_value=row)) for row in rows], None, None)

    def test_search_is_parameterized_and_read_only(self):
        query = "sistemas de informação ' DELETE p //"
        self.service.search_pages(query)
        args = self.driver.execute_query.call_args
        self.assertNotIn(query, args.args[0].text)
        self.assertEqual(args.kwargs['routing_'], 'r')
        self.assertEqual(args.kwargs['database_'], 'neo4j')
        self.assertIn('sistemas', args.kwargs['parameters_']['terms'])
        self.assertEqual(args.args[0].timeout, 8)

    def test_html_is_converted_to_text_and_script_is_removed(self):
        self.records([{'url': TARGET, 'title': 'SI', 'text': '', 'html': '<h1>Sistemas</h1><script>evil()</script><p>Informação &amp; cursos</p>'}])
        page = self.service.read_page(TARGET)
        self.assertIn('Informação & cursos', page['text'])
        self.assertNotIn('evil', page['text'])
        self.assertTrue(page['content_available'])
        self.assertNotIn('html', page)

    def test_page_without_html_is_explicit(self):
        self.records([{'url': TARGET, 'title': 'SI', 'text': '', 'html': ''}])
        self.assertFalse(self.service.read_page(TARGET)['content_available'])

    def test_url_validation_and_fragment(self):
        self.assertEqual(self.module.clean_url(TARGET + '#conteudo'), TARGET)
        for url in ['file:///secret', 'javascript:alert(1)', 'http://localhost/', 'https://puc-campinas.edu.br.evil.com/', 'https://user:pass@www.puc-campinas.edu.br/']:
            with self.assertRaises(ValueError):
                self.service.read_page(url)
        self.driver.execute_query.assert_not_called()

    def test_path_is_directed_and_bounded(self):
        self.service.navigation_path(BASE, TARGET)
        args = self.driver.execute_query.call_args
        self.assertIn('*1..15]->', args.args[0].text)
        self.assertIn(BASE, args.kwargs['parameters_']['start_urls'])
        for limit in [0, 100, '2', True]:
            with self.assertRaises(ValueError):
                self.service.navigation_path(BASE, TARGET, limit)

    def test_no_path_and_no_page(self):
        self.assertIsNone(self.service.navigation_path(BASE, TARGET))
        self.assertIsNone(self.service.read_page(BASE))

    def test_foreign_urls_in_results_are_not_exposed(self):
        self.records([{'url': 'https://evil.com/', 'title': 'invalid', 'text': 'x', 'html': ''}])
        self.assertEqual(self.service.search_pages('sistemas'), [])
        self.assertEqual(self.service.outgoing_links(BASE), [])

    def test_schema_is_configurable_and_rejects_cypher_injection(self):
        os.environ['NEO4J_PAGE_LABEL'] = 'Pagina'
        os.environ['NEO4J_URL_PROPERTY'] = 'endereco'
        configured = self.module.Neo4jService(self.driver)
        configured.read_page(BASE)
        self.assertIn('p:`Pagina`', self.driver.execute_query.call_args.args[0].text)
        self.assertIn('p.`endereco`', self.driver.execute_query.call_args.args[0].text)
        os.environ['NEO4J_PAGE_LABEL'] = 'Page`) DELETE p //'
        with self.assertRaises(ValueError):
            self.module.Neo4jService(self.driver)

    def test_missing_config_does_not_attempt_connection(self):
        with self.assertRaises(self.module.GraphConfigurationError):
            self.module.Neo4jService()

    def test_defaults_match_crawler_and_do_not_reference_missing_properties(self):
        self.service.search_pages('sistemas de informação')
        statement = self.driver.execute_query.call_args.args[0].text
        self.assertIn('p:`Pagina`', statement)
        self.assertIn('p.`descricao`', statement)
        self.assertIn('p.`restrita`', statement)
        self.assertNotIn('p.`text`', statement)
        self.service.outgoing_links(BASE)
        statement = self.driver.execute_query.call_args.args[0].text
        self.assertIn('r:`LINKA_PARA`', statement)
        self.assertNotIn('r.`text`', statement)

    def test_restricted_page_never_exposes_old_html(self):
        self.records([{'url': TARGET, 'title': 'Área restrita', 'restricted': True,
                       'text': 'Texto antigo', 'html': '<p>HTML antigo</p>'}])
        page = self.service.read_page(TARGET)
        self.assertTrue(page['restricted'])
        self.assertEqual(page['crawl_status'], 'restricted')
        self.assertEqual(page['text'], '')
        self.assertFalse(page['content_available'])
        statement = self.driver.execute_query.call_args.args[0].text
        self.assertIn('CASE WHEN p.`restrita` = true', statement)

    def test_discovered_node_is_not_assumed_restricted(self):
        self.records([{'url': TARGET, 'title': '', 'restricted': None, 'html': ''}])
        page = self.service.read_page(TARGET)
        self.assertIsNone(page['restricted'])
        self.assertEqual(page['crawl_status'], 'url_only')

    def test_initial_hash_route_is_preserved_and_document_fallback_is_explicit(self):
        seed = 'https://arealogada.sis.puc-campinas.edu.br/#/'
        self.records([{'url': seed, 'title': 'Portal', 'html': '<p>Portal</p>', 'restricted': False}])
        self.assertEqual(self.service.read_page(seed)['location_match'], 'exact')
        parameters = self.driver.execute_query.call_args.kwargs['parameters_']
        self.assertIn(seed, parameters['urls'])
        self.assertIn(seed.split('#')[0], parameters['urls'])
        result = self.service.read_page(seed + 'aluno')
        self.assertEqual(result['url'], seed)
        self.assertEqual(result['location_match'], 'document_only')
        self.assertEqual(result['requested_url'], seed + 'aluno')

    def test_same_document_path_has_zero_clicks(self):
        self.records([{'url': BASE, 'title': 'Início', 'html': '<p>Início</p>', 'restricted': False}])
        route = self.service.navigation_path(BASE + '#secao', BASE)
        self.assertEqual(route['click_count'], 0)
        self.assertEqual(route['link_texts'], [])
        self.assertEqual(route['scope'], 'mapped_documents')

    def test_user_variable_matches_crawler_and_legacy_alias_still_works(self):
        os.environ.update(NEO4J_URI='bolt://localhost:7687', NEO4J_PASSWORD='test-only', NEO4J_USER='crawler-user')
        self.assertTrue(self.module.configured())
        with patch('neo4j.GraphDatabase.driver') as create_driver:
            self.module.Neo4jService()
            self.assertEqual(create_driver.call_args.kwargs['auth'], ('crawler-user', 'test-only'))
            os.environ['NEO4J_USERNAME'] = 'legacy-user'
            del os.environ['NEO4J_USER']
            self.module.Neo4jService()
            self.assertEqual(create_driver.call_args.kwargs['auth'], ('legacy-user', 'test-only'))


class GraphToolsTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module('graph_tools_under_test', 'Services/tools/neo4j_tools.py', {})
        self.service = MagicMock()
        self.tools = self.module.build_neo4j_tools(BASE, service_factory=lambda: self.service)

    def test_tools_use_current_location(self):
        self.service.read_page.return_value = None
        self.tools[1]()
        self.service.read_page.assert_called_once_with(url=BASE)
        self.service.outgoing_links.return_value = []
        self.tools[2]()
        self.service.outgoing_links.assert_called_once_with(url=BASE)
        self.service.navigation_path.return_value = None
        self.tools[3](target_url=TARGET)
        self.service.navigation_path.assert_called_once_with(start_url=BASE, target_url=TARGET)

    def test_errors_and_not_found_are_distinct(self):
        self.service.search_pages.return_value = []
        self.assertEqual(json.loads(self.tools[0]('SI'))['status'], 'not_found')
        self.service.search_pages.side_effect = ValueError('Consulta inválida')
        self.assertEqual(json.loads(self.tools[0]('SI'))['status'], 'invalid_request')
        self.service.search_pages.side_effect = RuntimeError('private credentials')
        with self.assertLogs(self.module.__name__, level='ERROR'):
            response = json.loads(self.tools[0]('SI'))
        self.assertEqual(response['status'], 'unavailable')
        self.assertNotIn('private credentials', json.dumps(response))


class WebsiteAgentTests(unittest.TestCase):
    def setUp(self):
        self.generate = MagicMock()
        self.search, self.read, self.links, self.path = [MagicMock() for _ in range(4)]
        for tool, name in zip([self.search, self.read, self.links, self.path], ['search_site_pages','read_site_page','get_page_links','find_site_path']):
            tool.__name__ = name
        self.factory = MagicMock(return_value=[self.search, self.read, self.links, self.path])
        self.module = load_module('website_under_test', 'Agents/websiteAgent.py', {
            'Services.agents.specialist_agent': dependency('engine', generate_response=self.generate),
            'Services.tools.neo4j_tools': dependency('tools', build_neo4j_tools=self.factory),
        })

    def test_specialist_gets_all_graph_tools_location_and_history(self):
        self.generate.return_value = 'Resposta sem URL'
        history = [{'role': 'user', 'content': 'SI'}]
        self.module.website_agent({}, 'Como chegar?', current_url=BASE, history=history)
        args = self.generate.call_args.kwargs
        self.assertEqual(len(args['tools']), 5)
        self.assertEqual(json.loads(args['prompt'])['current_url'], BASE)
        self.assertEqual(args['history'], history)

    def test_fallback_consults_graph_and_returns_only_real_path(self):
        self.read.return_value = json.dumps({'status': 'not_found', 'data': None})
        self.search.return_value = json.dumps({'status':'ok','data':[{'url':TARGET,'title':'Sistemas de Informação','text':'Curso de tecnologia'}]})
        self.path.return_value = json.dumps({'status':'ok','data':{'pages':[{'url':BASE,'title':'Início'},{'url':TARGET,'title':'SI'}], 'link_texts':['Conheça SI']}})
        self.generate.side_effect = lambda *a, **kw: kw['fallback_tool'](query=kw['prompt'])
        answer = self.module.website_agent({}, 'curso SI', current_url=BASE)
        self.assertIn(TARGET, answer)
        self.assertIn('Conheça SI', answer)
        self.assertIn('Caminho mapeado', answer)

    def test_no_path_does_not_invent_clicks(self):
        self.read.return_value = json.dumps({'status': 'not_found', 'data': None})
        self.search.return_value = json.dumps({'status':'ok','data':[{'url':TARGET,'title':'SI','text':''}]})
        self.path.return_value = json.dumps({'status':'not_found','data':None})
        self.generate.side_effect = lambda *a, **kw: kw['fallback_tool'](query=kw['prompt'])
        answer = self.module.website_agent({}, 'curso SI', current_url=BASE)
        self.assertIn('não há texto salvo', answer)
        self.assertIn('Não encontrei um caminho', answer)

    def test_restricted_page_is_identified_in_fallback(self):
        self.read.return_value = json.dumps({'status': 'not_found', 'data': None})
        self.search.return_value = json.dumps({'status':'ok','data':[{'url':TARGET,'title':'Área restrita','text':'HTML antigo', 'restricted':True}]})
        self.path.return_value = json.dumps({'status':'not_found','data':None})
        self.generate.side_effect = lambda *a, **kw: kw['fallback_tool'](query=kw['prompt'])
        answer = self.module.website_agent({}, 'curso SI', current_url=BASE)
        self.assertIn('Página marcada como restrita', answer)
        self.assertNotIn('HTML antigo', answer)


if __name__ == '__main__':
    unittest.main()
