from Services.orm.search import search_knowledge_base


def search_chroma(query: str) -> str:
    """
    Pesquisa informações na base de conhecimento.

    Args:
        query: Pergunta ou assunto que deve ser pesquisado.
    """
    results = search_knowledge_base(query, top_k=5)

    return "\n\n".join(results) if results else "Nenhum documento encontrado."