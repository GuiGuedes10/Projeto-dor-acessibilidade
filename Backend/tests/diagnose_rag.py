"""Diagnóstico local: python tests/diagnose_rag.py --cpu --context-file tests/fixtures/sbi.json"""
import argparse
import json
import os
from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query', default='A SBI possui serviços de inclusão para deficiente visual? como livros em braile')
    parser.add_argument('--context-file', type=Path, help='JSON com lista de textos ou evidências; evita carregar embeddings e banco')
    parser.add_argument('--cpu', action='store_true', help='Carrega o modelo sem quantização na CPU')
    parser.add_argument('--retrieval-only', action='store_true', help='Consulta a base sem carregar a LLM')
    parser.add_argument('--output', type=Path, help='Salva o diagnóstico completo em JSON')
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.path.insert(0, str(BACKEND))
    evidence = None
    if args.context_file:
        values = json.loads(args.context_file.read_text(encoding='utf-8-sig'))
        evidence = [{'text': item, 'source': 'Contexto fornecido para diagnóstico', 'page': None}
                    if isinstance(item, str) else item for item in values]
    os.chdir(BACKEND)
    from dotenv import load_dotenv
    load_dotenv(BACKEND / '.env')
    from Agents.ragAgent import diagnose_rag
    if args.retrieval_only:
        from Services.orm.search import search_evidence
        if evidence is None:
            evidence = search_evidence(args.query)
        report = {'query': args.query, 'status': 'retrieval_only', 'evidence': evidence}
    else:
        print('Carregando modelo...', flush=True)
        if args.cpu:
            import torch
            from transformers import AutoTokenizer, AutoModelForCausalLM
            torch.set_num_threads(min(4, os.cpu_count() or 1))
            model_name = os.environ['MODEL_AGENTE_NAME']
            llm = {'tokenizer': AutoTokenizer.from_pretrained(model_name),
                   'model': AutoModelForCausalLM.from_pretrained(model_name, device_map='cpu')}
            llm['model'].eval()
        else:
            from Models.llm import load_llm
            llm = load_llm()
        print('Executando RAG...', flush=True)
        report = diagnose_rag(llm, args.query, evidence=evidence)
        report['model'] = os.environ.get('MODEL_AGENTE_NAME')
        report['execution'] = 'cpu_unquantized' if args.cpu else 'configured_quantization'
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    print(serialized)
    if args.output:
        args.output.resolve().write_text(serialized, encoding='utf-8')


if __name__ == '__main__':
    main()
