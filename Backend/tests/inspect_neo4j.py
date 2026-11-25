"""Inspeciona o Neo4j sem iniciar a API, Redis ou modelos."""
import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schema', action='store_true', help='Exibe labels, propriedades e tipos de relações')
    parser.add_argument('--search', help='Palavras-chave para buscar páginas')
    parser.add_argument('--url', help='URL para ler o conteúdo salvo e links de saída')
    parser.add_argument('--from-url', help='Origem de um caminho dirigido')
    parser.add_argument('--to-url', help='Destino de um caminho dirigido')
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    from Services.Neo4j.neo4j_service import get_service
    try:
        service = get_service()
        output = {}
        if args.schema or not any([args.search, args.url, args.from_url, args.to_url]):
            output['nodes'] = service._read('MATCH (n) RETURN DISTINCT labels(n) AS labels, keys(n) AS properties LIMIT 20')
            output['relationships'] = service._read('MATCH (a)-[r]->(b) RETURN DISTINCT labels(a) AS source, type(r) AS relationship, keys(r) AS properties, labels(b) AS target LIMIT 20')
        if args.search:
            output['pages'] = service.search_pages(args.search)
        if args.url:
            output['page'] = service.read_page(args.url)
            output['links'] = service.outgoing_links(args.url)
        if args.from_url and args.to_url:
            output['path'] = service.navigation_path(args.from_url, args.to_url)
        elif args.from_url or args.to_url:
            parser.error('Use --from-url e --to-url juntos.')
        print(json.dumps(output, ensure_ascii=False, indent=2))
    except Exception as error:
        print(f'Falha ao consultar o Neo4j ({type(error).__name__}). Confira credenciais, conexão e nomes do esquema no .env.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
