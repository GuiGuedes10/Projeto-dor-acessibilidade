"""Política de domínio e compatibilidade com URLs gravadas pelo crawler."""
import os
from urllib.parse import urlsplit
from Utils.url_utils import clean_url as normalize_url


def clean_url(value, *, keep_fragment=False):
    domains = os.getenv('NEO4J_ALLOWED_DOMAINS', 'puc-campinas.edu.br').split(',')
    return normalize_url(value, keep_fragment=keep_fragment, allowed_domains=domains)


def url_candidates(value):
    # O crawler manteve #/ na semente, mas removeu fragmentos dos links extraídos.
    exact, document = clean_url(value, keep_fragment=True), clean_url(value)
    candidates = [exact, document]
    if urlsplit(document).path == '/':
        candidates.append(document + '#/')
    return list(dict.fromkeys(candidates))
