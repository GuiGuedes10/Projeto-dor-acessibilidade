import json
from Services.orm.search import search_evidence


def search_chroma(query: str) -> str:
    """
    Pesquisa informações na base de conhecimento.

    Args:
        query: Pergunta ou assunto que deve ser pesquisado.
    """
    results = search_evidence(query, top_k=5)

    return json.dumps(results, ensure_ascii=False) if results else "Nenhum documento encontrado."
