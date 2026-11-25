"""Ferramentas do especialista para consultar páginas e conexões do Neo4j."""
import json
import logging


def build_neo4j_tools(current_url=None, *, service_factory=None, on_result=None):
    if service_factory is None:
        from Services.Neo4j.neo4j_service import get_service
        service_factory = get_service

    def invoke(operation, **arguments):
        try:
            data = getattr(service_factory(), operation)(**arguments)
            result = {'status': 'ok' if data else 'not_found', 'data': data}
        except ValueError as error:
            result = {'status': 'invalid_request', 'message': str(error), 'data': None}
        except Exception:
            logging.getLogger(__name__).exception('Falha na consulta Neo4j: %s', operation)
            result = {'status': 'unavailable', 'message': 'Não foi possível consultar o mapa do site.', 'data': None}
        if on_result:
            on_result(operation, result)
        return json.dumps(result, ensure_ascii=False)

    def search_site_pages(query: str) -> str:
        """Busca páginas do site parceiro por palavras-chave, descrições e conteúdo.

        Args:
            query: Palavras-chave específicas, por exemplo sistemas de informação.
        """
        return invoke('search_pages', query=query)

    def read_site_page(url: str = '') -> str:
        """Lê o texto ou HTML salvo de uma página. Vazio usa a página atual.

        Args:
            url: URL da página, ou vazio para a URL atual do navegador.
        """
        return invoke('read_page', url=url or current_url or '')

    def get_page_links(url: str = '') -> str:
        """Lista links de saída mapeados, mostrando para onde é possível navegar.

        Args:
            url: URL de origem, ou vazio para usar a página atual.
        """
        return invoke('outgoing_links', url=url or current_url or '')

    def find_site_path(target_url: str, start_url: str = '') -> str:
        """Procura um caminho de cliques dirigido entre duas páginas do grafo.

        Args:
            target_url: URL de destino encontrada no mapa do site.
            start_url: URL de origem, ou vazio para usar a página atual.
        """
        return invoke('navigation_path', start_url=start_url or current_url or '', target_url=target_url)

    return [search_site_pages, read_site_page, get_page_links, find_site_path]
