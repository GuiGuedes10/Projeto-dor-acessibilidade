"""Inspeciona o Chroma existente sem iniciar a API, ingerir PDFs ou carregar modelos.

Execute, a partir de Backend:
    python tests/test_orm.py
    python tests/test_orm.py --contains "matrícula" --full
    python tests/test_orm.py --source "manual-candidato-vestibular-1.pdf"
    python tests/test_orm.py --limit 10 --offset 10 --json
"""
import argparse
import json
from pathlib import Path
import sys


DEFAULT_DB = Path(__file__).resolve().parents[1] / "chroma_db"


def inspect_database(db_path: Path, collection_name: str, *, limit: int = 5,
                     offset: int = 0, contains: str | None = None,
                     source: str | None = None) -> dict:
    if limit < 1 or offset < 0:
        raise ValueError("limit deve ser positivo e offset não pode ser negativo.")
    db_path = db_path.resolve()
    # Não cria um banco vazio por engano ao receber um caminho incorreto.
    if not (db_path / "chroma.sqlite3").is_file():
        raise ValueError(f"Banco Chroma não encontrado em: {db_path}")

    import chromadb

    client = chromadb.PersistentClient(path=str(db_path))
    collection = client.get_collection(name=collection_name)
    filters = {}
    if contains:
        filters["where_document"] = {"$contains": contains}
    if source:
        filters["where"] = {"source": source}
    results = collection.get(
        limit=limit, offset=offset, include=["documents", "metadatas"], **filters,
    )
    return {
        "database": str(db_path),
        "collection": collection.name,
        "total_records": collection.count(),
        "offset": offset,
        "records": [
            {"id": identifier, "metadata": metadata or {}, "text": text or ""}
            for identifier, metadata, text in zip(
                results["ids"], results["metadatas"], results["documents"],
            )
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Pasta do banco Chroma")
    parser.add_argument("--collection", default="knowledge_base")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--contains", help="Filtra texto literal (diferencia maiúsculas e minúsculas)")
    parser.add_argument("--source", help="Nome exato do PDF nos metadados; requer índice atualizado")
    parser.add_argument("--full", action="store_true", help="Exibe o texto completo de cada trecho")
    parser.add_argument("--json", action="store_true", help="Exibe todos os campos e textos em JSON")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        data = inspect_database(args.db, args.collection, limit=args.limit,
                                offset=args.offset, contains=args.contains, source=args.source)
    except Exception as error:
        print(f"Não foi possível consultar o banco: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    print(f"Banco: {data['database']}\nColeção: {data['collection']}")
    print(f"Total na coleção: {data['total_records']} | Exibidos: {len(data['records'])}")
    for record in data["records"]:
        print(f"\nID: {record['id']}")
        print("Metadados:", json.dumps(record["metadata"], ensure_ascii=False))
        text = record["text"]
        print(text if args.full or len(text) <= 400 else text[:400] + "…")
    if not data["records"]:
        print("Nenhum registro encontrado para os filtros e a página solicitados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
