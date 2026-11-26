"""Configuração e nomes do esquema do grafo."""
import os
from pathlib import Path
import re
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


class Neo4jConfig:
    def __init__(self):
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
