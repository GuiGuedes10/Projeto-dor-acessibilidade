"""Fachada das operações do mapa do site: páginas, links e caminhos."""
from functools import lru_cache

from Services.Neo4j.config import Neo4jConfig, GraphConfigurationError, configured, username
from Services.Neo4j.connection import Neo4jConnection
from Services.Neo4j import queries
from Services.Neo4j.pages import format_page
from Services.Neo4j.urls import clean_url, url_candidates
from Utils.text_utils import keyword_terms


class Neo4jService:
    def __init__(self, driver=None):
        self.config = Neo4jConfig()
        self.connection = Neo4jConnection(self.config, driver=driver)
        self.driver = self.connection.driver

    def _read(self, statement, **parameters):
        return self.connection.read(statement, **parameters)

    def projection(self, alias='p'):
        return queries.projection(self.config, alias)

    page = staticmethod(format_page)

    def read_page(self, url):
        requested_url = clean_url(url, keep_fragment=True)
        records = self._read(queries.read_page_query(self.config), urls=url_candidates(url), requested_url=requested_url, content_limit=10000, html_limit=120000)
        page = self.page(records[0]) if records else None
        if page:
            page.update(requested_url=requested_url, location_match='exact' if requested_url == page['url'] else 'document_only')
        return page

    def search_pages(self, query, limit=5):
        if not isinstance(query, str) or not query.strip():
            raise ValueError('Informe palavras-chave para pesquisar páginas.')
        if not isinstance(limit, int) or isinstance(limit, bool) or (not 1 <= limit <= 10):
            raise ValueError('O limite deve estar entre 1 e 10.')
        terms = keyword_terms(query, stopwords=queries.SEARCH_STOPWORDS)
        if not terms:
            return []
        records = self._read(queries.search_pages_query(self.config), terms=terms, pairs=queries.DIACRITICS, limit=limit, content_limit=2000, html_limit=20000)
        return [page for record in records if (page := self.page(record)) is not None]

    def outgoing_links(self, url, limit=20):
        if not isinstance(limit, int) or isinstance(limit, bool) or (not 1 <= limit <= 50):
            raise ValueError('O limite de links deve estar entre 1 e 50.')
        records = self._read(queries.outgoing_links_query(self.config), urls=url_candidates(url), limit=limit)
        links = []
        for record in records:
            try:
                record['url'] = clean_url(record['url'], keep_fragment=True)
            except (ValueError, TypeError, KeyError):
                continue
            links.append(record)
        return links

    def navigation_path(self, start_url, target_url, max_hops=None):
        max_hops = self.config.max_hops if max_hops is None else max_hops
        if not isinstance(max_hops, int) or isinstance(max_hops, bool) or (not 1 <= max_hops <= 30):
            raise ValueError('max_hops deve estar entre 1 e 30.')
        starts, targets = (url_candidates(start_url), url_candidates(target_url))
        if set(starts) & set(targets):
            page = self.read_page(start_url)
            if page:
                return {'pages': [{key: page[key] for key in ('url', 'title', 'restricted')}], 'link_texts': [], 'click_count': 0, 'scope': 'mapped_documents'}
            return None
        records = self._read(queries.navigation_path_query(self.config, max_hops), start_urls=starts, target_urls=targets)
        if not records:
            return None
        result = records[0]
        try:
            for page in result['pages']:
                page['url'] = clean_url(page['url'], keep_fragment=True)
        except (ValueError, TypeError, KeyError):
            return None
        return {**result, 'scope': 'mapped_documents'}


@lru_cache(maxsize=1)
def get_service():
    return Neo4jService()
