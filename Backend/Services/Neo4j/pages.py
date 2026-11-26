"""Formatação de páginas e tratamento de conteúdo restrito."""
from Services.Neo4j.urls import clean_url
from Utils.html_utils import html_text


def format_page(record):
    try:
        url = clean_url(record['url'], keep_fragment=True)
    except (ValueError, TypeError, KeyError):
        return None
    restricted = record.get('restricted')
    text = '' if restricted is True else ((record.get('text') or '').strip() or html_text(record.get('html')))
    return {'url': url, 'title': record.get('title') or '', 'text': text[:10000],
            'content_available': bool(text), 'restricted': restricted,
            'crawl_status': 'restricted' if restricted is True else 'captured' if record.get('html') or record.get('text') else 'url_only'}
