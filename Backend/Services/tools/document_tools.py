"""Ferramenta de recuperação dos PDFs, com fontes e estado por execução."""
import json
import logging


def build_document_tool(documents, *, search=None, on_result=None):
    def retrieve(query, top_k):
        if search is not None:
            return search(query, top_k=top_k)
        from Services.orm.search import search_evidence
        return search_evidence(query, top_k=top_k)

    def search_documents(query: str) -> str:
        """Recupera trechos dos PDFs institucionais, com identificação da fonte.

        Args:
            query: Pergunta ou assunto a pesquisar nos documentos.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError('Informe uma pergunta para consultar os documentos.')
        try:
            evidence = retrieve(query.strip(), top_k=5)
        except Exception:
            logging.getLogger(__name__).exception('Falha na consulta aos documentos')
            result = {'status': 'unavailable', 'data': None}
            if on_result:
                on_result('search_documents', result)
            return json.dumps(result)
        results = []
        for item in evidence:
            document = dict(item)
            document['id'] = len(documents) + 1
            documents.append(document)
            results.append(document)
        result = {'status': 'ok' if results else 'not_found', 'data': results}
        if on_result:
            on_result('search_documents', result)
        return json.dumps(result, ensure_ascii=False)


    return search_documents
