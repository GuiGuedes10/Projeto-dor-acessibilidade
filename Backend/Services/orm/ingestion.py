import hashlib
from pathlib import Path

from Services.orm.pdfReader import read_pdf_pages
from Services.orm.chunker import split_text
from Services.orm.embedding import generate_embeddings
from Database.chromaDb.chroma import collection



PDF_FOLDER = Path(__file__).resolve().parents[2] / "Database" / "chromaDb" / "datas"


def load_pdfs() -> list[Path]:
    return list(PDF_FOLDER.glob("*.pdf"))


def save_embeddings(
    chunks: list[str],
    embeddings: list[list[float]],
    ids: list[str],
    metadatas: list[dict]
):
    collection.upsert(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas
    )


def process_pdf(path: Path):

    file_hash = hashlib.sha256(path.read_bytes()).hexdigest()

    file_prefix = hashlib.sha256(
        str(path.resolve()).encode()
    ).hexdigest()[:16]

    chunks = []
    metadatas = []
    for page, text in read_pdf_pages(str(path)):
        for chunk in split_text(text):
            chunks.append(chunk)
            metadatas.append({"source": path.name, "page": page, "file_hash": file_hash})

    if not chunks:
        print(f"Nenhum texto encontrado: {path.name}")
        return False

    ids = [
        f"{file_prefix}_{file_hash}_v2_{i}"
        for i in range(len(chunks))
    ]

    existing_ids = collection.get(
        where=None
    )["ids"]

    previous_ids = [
        item for item in existing_ids
        if item.startswith(f"{file_prefix}_")
    ]

    if set(ids).issubset(set(previous_ids)):
        print(f"Documento já carregado: {path.name}")
        return True

    embeddings = generate_embeddings(chunks)

    save_embeddings(chunks, embeddings, ids, metadatas)

    stale_ids = sorted(set(previous_ids) - set(ids))
    if stale_ids:
        collection.delete(ids=stale_ids)

    print(f"Documento carregado: {path.name}")
    return True


def initialize_knowledge_base():

    PDF_FOLDER.mkdir(parents=True, exist_ok=True)

    pdfs = load_pdfs()

    if not pdfs:
        print("Nenhum PDF encontrado.")
        return

    seen_hashes = set()
    for pdf in sorted(pdfs):
        file_hash = hashlib.sha256(pdf.read_bytes()).hexdigest()
        if file_hash in seen_hashes:
            # A cópia canônica já foi salva; remove entradas antigas desta cópia.
            prefix = hashlib.sha256(str(pdf.resolve()).encode()).hexdigest()[:16]
            duplicate_ids = [identifier for identifier in collection.get(include=[])["ids"]
                             if identifier.startswith(f"{prefix}_")]
            if duplicate_ids:
                collection.delete(ids=duplicate_ids)
            print(f"PDF duplicado ignorado: {pdf.name}")
            continue
        if process_pdf(pdf):
            seen_hashes.add(file_hash)

    print("Base de conhecimento inicializada.")
