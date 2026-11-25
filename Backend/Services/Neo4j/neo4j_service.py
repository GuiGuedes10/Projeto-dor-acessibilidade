"""Consultas parametrizadas de leitura ao mapa de páginas do site parceiro."""
import atexit
from functools import lru_cache
from html.parser import HTMLParser
import os
from pathlib import Path
import re
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / '.env')


class GraphConfigurationError(ValueError):
    pass


def configured():
    return bool(os.getenv('NEO4J_URI', '').strip() and username() and os.getenv('NEO4J_PASSWORD', '').strip())


def username():
    return os.getenv('NEO4J_USER', '').strip() or os.getenv('NEO4J_USERNAME', '').strip()


def identifier(name, default):
    value = os.getenv(name, default)
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', value):
        raise GraphConfigurationError(f'{name} deve ser um identificador simples do Cypher.')
    return f'`{value}`'


def optional_identifier(name):
    return identifier(name, '') if os.getenv(name, '').strip() else None


def clean_url(value, *, keep_fragment=False):
    parts = urlsplit(value.strip())
    if parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username or parts.password:
        raise ValueError('Informe uma URL HTTP ou HTTPS válida, sem credenciais.')
    domains = [item.strip().lower() for item in os.getenv('NEO4J_ALLOWED_DOMAINS', 'puc-campinas.edu.br').split(',') if item.strip()]
    host = parts.hostname.lower()
    if not any(host == domain or host.endswith('.' + domain) for domain in domains):
        raise ValueError('A URL não pertence ao site parceiro configurado.')
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path or '/', parts.query,
                       parts.fragment if keep_fragment else ''))


def url_candidates(value):
    # O crawler manteve #/ na semente, mas removeu fragmentos dos links extraídos.
    exact, document = clean_url(value, keep_fragment=True), clean_url(value)
    candidates = [exact, document]
    if urlsplit(document).path == '/':
        candidates.append(document + '#/')
    return list(dict.fromkeys(candidates))


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ignored = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'noscript', 'template'}:
            self.ignored += 1
        elif tag in {'p', 'div', 'br', 'li', 'h1', 'h2', 'h3', 'tr', 'section'}:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript', 'template'} and self.ignored:
            self.ignored -= 1
        elif not self.ignored:
            self.parts.append(' ')

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


def html_text(html):
    parser = TextExtractor()
    parser.feed((html or '')[:120000])
    return re.sub(r'\s+', ' ', ''.join(parser.parts)).strip()[:10000]


class Neo4jService:
    def __init__(self, driver=None):
        self.label = identifier('NEO4J_PAGE_LABEL', 'Pagina')
        self.url = identifier('NEO4J_URL_PROPERTY', 'url')
        self.title = identifier('NEO4J_TITLE_PROPERTY', 'descricao')
        self.html = identifier('NEO4J_HTML_PROPERTY', 'html')
        self.text = optional_identifier('NEO4J_TEXT_PROPERTY')
        self.restricted = identifier('NEO4J_RESTRICTED_PROPERTY', 'restrita')
        self.relation = identifier('NEO4J_LINK_RELATION', 'LINKA_PARA')
        self.link_text = optional_identifier('NEO4J_LINK_TEXT_PROPERTY')
        self.max_hops = int(os.getenv('NEO4J_MAX_HOPS', '15'))
        if not 1 <= self.max_hops <= 30:
            raise GraphConfigurationError('NEO4J_MAX_HOPS deve estar entre 1 e 30.')
        self.database = os.getenv('NEO4J_DATABASE', 'neo4j')
        self.timeout = float(os.getenv('NEO4J_QUERY_TIMEOUT', '8'))
        if not 0 < self.timeout <= 60:
            raise GraphConfigurationError('NEO4J_QUERY_TIMEOUT deve estar entre 0 e 60 segundos.')
        if driver is None:
            if not configured():
                raise GraphConfigurationError('Configure NEO4J_URI, NEO4J_USER e NEO4J_PASSWORD.')
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(os.environ['NEO4J_URI'],
                auth=(username(), os.environ['NEO4J_PASSWORD']),
                connection_timeout=5, max_transaction_retry_time=5)
            atexit.register(driver.close)
        self.driver = driver

    def _read(self, statement, **parameters):
        from neo4j import Query
        records, _, _ = self.driver.execute_query(Query(statement, timeout=self.timeout),
            parameters_=parameters, database_=self.database, routing_='r')
        return [record.data() for record in records]

    def projection(self, alias='p'):
        text = f'coalesce({alias}.{self.text}, "")' if self.text else '""'
        return (f'{alias}.{self.url} AS url, coalesce({alias}.{self.title}, "") AS title, '
                f'{alias}.{self.restricted} AS restricted, '
                f'CASE WHEN {alias}.{self.restricted} = true THEN "" ELSE substring({text}, 0, $content_limit) END AS text, '
                f'CASE WHEN {alias}.{self.restricted} = true THEN "" ELSE substring(coalesce({alias}.{self.html}, ""), 0, $html_limit) END AS html')

    @staticmethod
    def page(record):
        try:
            url = clean_url(record['url'], keep_fragment=True)
        except (ValueError, TypeError, KeyError):
            return None
        restricted = record.get('restricted')
        text = '' if restricted is True else ((record.get('text') or '').strip() or html_text(record.get('html')))
        return {'url': url, 'title': record.get('title') or '', 'text': text[:10000],
                'content_available': bool(text), 'restricted': restricted,
                'crawl_status': 'restricted' if restricted is True else 'captured' if record.get('html') or record.get('text') else 'url_only'}

    def read_page(self, url):
        requested_url = clean_url(url, keep_fragment=True)
        records = self._read(f'MATCH (p:{self.label}) WHERE p.{self.url} IN $urls '
                             f'RETURN {self.projection()} ORDER BY CASE WHEN p.{self.url} = $requested_url THEN 0 ELSE 1 END, url LIMIT 1',
                             urls=url_candidates(url), requested_url=requested_url,
                             content_limit=10000, html_limit=120000)
        page = self.page(records[0]) if records else None
        if page:
            page.update(requested_url=requested_url,
                        location_match='exact' if requested_url == page['url'] else 'document_only')
        return page

    def search_pages(self, query, limit=5):
        if not isinstance(query, str) or not query.strip():
            raise ValueError('Informe palavras-chave para pesquisar páginas.')
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 10:
            raise ValueError('O limite deve estar entre 1 e 10.')
        stop = {'a', 'o', 'os', 'as', 'de', 'da', 'do', 'das', 'dos', 'em', 'e', 'que', 'no', 'na', 'tem', 'como', 'para', 'puc'}
        terms = [term for term in re.findall(r'\w+', query.casefold()) if len(term) > 1 and term not in stop][:12]
        if not terms:
            return []
        # Normaliza acentos dos dois lados sem depender de APOC ou de índices externos.
        pairs = [['á','a'], ['à','a'], ['ã','a'], ['â','a'], ['é','e'], ['ê','e'], ['í','i'], ['ó','o'], ['ô','o'], ['õ','o'], ['ú','u'], ['ç','c']]
        text_expression = f'coalesce(p.{self.text}, "")' if self.text else '""'
        statement = f'''MATCH (p:{self.label})
WITH p, reduce(t = toLower(coalesce(p.{self.title}, '') + ' ' + coalesce(p.{self.url}, '') + ' ' +
    CASE WHEN p.{self.restricted} = true THEN '' ELSE
    substring({text_expression}, 0, 20000) + ' ' + substring(coalesce(p.{self.html}, ''), 0, 20000) END),
    pair IN $pairs | replace(t, pair[0], pair[1])) AS searchable
WITH p, [term IN $terms WHERE searchable CONTAINS reduce(t = term, pair IN $pairs | replace(t, pair[0], pair[1]))] AS hits
WHERE size(hits) > 0
RETURN {self.projection()}, size(hits) AS score
ORDER BY score DESC, url ASC LIMIT $limit'''
        records = self._read(statement, terms=terms, pairs=pairs, limit=limit,
                             content_limit=2000, html_limit=20000)
        return [page for record in records if (page := self.page(record)) is not None]

    def outgoing_links(self, url, limit=20):
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
            raise ValueError('O limite de links deve estar entre 1 e 50.')
        link_text = f'coalesce(r.{self.link_text}, "")' if self.link_text else '""'
        records = self._read(f'''MATCH (p:{self.label})-[r:{self.relation}]->(dest:{self.label})
WHERE p.{self.url} IN $urls
RETURN DISTINCT dest.{self.url} AS url, coalesce(dest.{self.title}, '') AS title,
dest.{self.restricted} AS restricted, {link_text} AS link_text ORDER BY url LIMIT $limit''', urls=url_candidates(url), limit=limit)
        links = []
        for record in records:
            try:
                record['url'] = clean_url(record['url'], keep_fragment=True)
            except (ValueError, TypeError, KeyError):
                continue
            links.append(record)
        return links

    def navigation_path(self, start_url, target_url, max_hops=None):
        max_hops = self.max_hops if max_hops is None else max_hops
        if not isinstance(max_hops, int) or isinstance(max_hops, bool) or not 1 <= max_hops <= 30:
            raise ValueError('max_hops deve estar entre 1 e 30.')
        starts, targets = url_candidates(start_url), url_candidates(target_url)
        if set(starts) & set(targets):
            page = self.read_page(start_url)
            if page:
                return {'pages': [{key: page[key] for key in ('url', 'title', 'restricted')}],
                        'link_texts': [], 'click_count': 0, 'scope': 'mapped_documents'}
            return None
        link_text = f'coalesce(rel.{self.link_text}, "")' if self.link_text else '""'
        # Somente links dirigidos: uma ligação A->B não permite inferir um clique B->A.
        records = self._read(f'''MATCH (start:{self.label}), (target:{self.label})
WHERE start.{self.url} IN $start_urls AND target.{self.url} IN $target_urls
MATCH path = shortestPath((start)-[:{self.relation}*1..{max_hops}]->(target))
RETURN [node IN nodes(path) | {{url: node.{self.url}, title: coalesce(node.{self.title}, ''), restricted: node.{self.restricted}}}] AS pages,
[rel IN relationships(path) | {link_text}] AS link_texts, length(path) AS click_count
ORDER BY click_count ASC LIMIT 1''', start_urls=starts, target_urls=targets)
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
