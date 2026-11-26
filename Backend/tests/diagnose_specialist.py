"""Diagnóstico do especialista real, sem iniciar a API.
Exemplo controlado: python tests/diagnose_specialist.py --fixture tests/fixtures/sbi.json
Sem --fixture, usa as fontes reais configuradas no backend.
"""
import argparse
import json
import os
from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query', default='A SBI possui livros em Braille?')
    parser.add_argument('--url')
    parser.add_argument('--fixture', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--max-new-tokens', type=int, default=128)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text(encoding='utf-8-sig')) if args.fixture else None
    output = args.output.resolve() if args.output else None
    sys.path.insert(0, str(BACKEND))
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    os.chdir(BACKEND)
    from Models.llm import load_llm
    import torch
    from Agents import ragAgent
    from Services.agents import specialist_agent as engine
    from Services.tools.neo4j_tools import build_neo4j_tools
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    print('Carregando o modelo...', flush=True)
    llm = load_llm()
    llm['max_new_tokens'] = args.max_new_tokens
    turns, calls = [], []
    original_turn = engine.generate_turn
    original_search = ragAgent.search_evidence
    original_graph = ragAgent.build_graph_tools

    def trace_turn(*values, **kwargs):
        print(f'Gerando etapa {len(turns) + 1}...', flush=True)
        response = original_turn(*values, **kwargs)
        turns.append(response)
        print(f'Geração {len(turns)}: {response}', flush=True)
        return response

    def trace_search(query, top_k=5):
        if fixture is not None:
            result = [{'source': 'Contexto controlado', 'page': None, 'text': text} for text in fixture][:top_k]
        else:
            result = original_search(query, top_k=top_k)
        calls.append({'tool': 'search_documents', 'query': query, 'result_count': len(result)})
        return result

    class EmptyGraph:
        def __getattr__(self, name):
            return lambda **kw: None

    def trace_graph(url, on_result):
        def record(operation, result):
            calls.append({'tool': operation, 'status': result['status']})
            on_result(operation, result)
        if fixture is not None:
            return build_neo4j_tools(url, service_factory=EmptyGraph, on_result=record)
        return original_graph(url, record)

    engine.generate_turn = trace_turn
    ragAgent.search_evidence = trace_search
    ragAgent.build_graph_tools = trace_graph
    try:
        response = ragAgent.rag_agent(llm, args.query, current_url=args.url)
    finally:
        engine.generate_turn = original_turn
        ragAgent.search_evidence = original_search
        ragAgent.build_graph_tools = original_graph
    report = {'query': args.query, 'fixture': fixture is not None, 'model': os.getenv('MODEL_AGENTE_NAME'),
              'turns': turns, 'calls': calls, 'response': response}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if output:
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
