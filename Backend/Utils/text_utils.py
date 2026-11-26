"""Preparação de palavras-chave independente de banco ou modelo."""
import re


def keyword_terms(query, *, stopwords=(), limit=12):
    return [term for term in re.findall(r'\w+', query.casefold())
            if len(term) > 1 and term not in stopwords][:limit]
